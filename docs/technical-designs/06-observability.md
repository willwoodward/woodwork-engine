---
title: Observability (EventBus)
description: How hooks, pipes, and the EventBus provide observability without coupling components
index: 5
---

# Observability: EventBus

Woodwork's observability layer is built on a lightweight `EventBus` (`woodwork/core/events.py`). It is **not** a message-routing bus — components call each other directly. The event bus is for side-effects: logging, debugging, transforming payloads.

## Three Listener Types

| Type | Execution | Can modify payload? | Use for |
|------|-----------|-------------------|---------|
| **Hook** | Concurrent | No | Logging, metrics, alerts |
| **Pipe** | Sequential | Yes (returns new payload) | Data enrichment, validation |
| **Event** | Fire-and-forget | No | Async side effects |

### Hooks — concurrent, read-only

All hooks for an event run concurrently via `asyncio.gather`. The payload is passed in but the return value is ignored.

```python
async def log_tool_call(payload):
    print(f"[tool] {payload['tool']} called with {payload['args']}")
```

### Pipes — sequential, transforming

Pipes run in declaration order. Each receives the (possibly already-transformed) payload and returns a new one. If a pipe returns `None`, the payload is passed through unchanged.

```python
def add_context(payload):
    return {**payload, "timestamp": time.time()}
```

### Events — fire-and-forget

Scheduled as asyncio tasks. Used when you need async side-effects that shouldn't block the main flow.

## EventBus Hierarchy

Each `LLMAgent` owns its own `EventBus`. The system-level bus is passed to the agent at construction, and becomes its **parent**:

```python
self.event_bus = EventBus(parent=system_bus)
```

Every `emit()` on the agent bus automatically bubbles up:

```python
async def emit(self, event, payload):
    await self._run_hooks(event, payload)
    payload = await self._run_pipes(event, payload)
    self._fire_events(event, payload)
    if self._parent:
        await self._parent.emit(event, payload)   # bubble
    return payload
```

This means a system-level listener on `AsyncRuntime.system_bus` observes events from all agents without any agent needing to know about it.

```
system_bus  (AsyncRuntime)
    │
    ├── agent_bus (LLMAgent "assistant")
    │       emits: agent.thought, tool.call, tool.observation, ...
    │
    └── agent_bus (LLMAgent "researcher")
            emits: agent.thought, tool.call, ...
```

## Registering Hooks and Pipes in .ww Config

```ww
assistant = agent llm {
    model: model

    hooks = [
        { event: "tool.call", function: "log_tool", script: "hooks/logging.py" }
    ]

    pipes = [
        { event: "agent.action", function: "add_metadata", script: "pipes/meta.py" }
    ]
}
```

During `LLMAgent.start()`, `_register_hooks_pipes(self.event_bus)` loads each function from its script file and registers it on the agent's bus.

## Standard Events

Emitted by `AgentLoop`:

| Event | Payload | When |
|-------|---------|------|
| `agent.thought` | `{"thought": str}` | After each non-final LLM thought |
| `agent.action` | `{"action": dict}` | Before each tool call (pipeable) |
| `tool.call` | `{"tool": str, "args": dict}` | When a tool is invoked |
| `tool.observation` | `{"tool": str, "observation": str}` | After a tool returns |
| `agent.step_complete` | `{"step": int}` | After each iteration |
| `agent.error` | `{"error": str, "tool": str}` | When a tool raises |

## Programmatic Registration

You can also register listeners directly at runtime:

```python
agent.event_bus.register_hook("tool.call", my_hook_fn)
agent.event_bus.register_pipe("agent.action", my_pipe_fn)
```

This is useful for test harnesses, eval runners, or runtime monitoring.

## Eval Runner

`woodwork/eval/runner.py` uses this to collect a trace of all events during an agent run:

```python
trace = []
agent.event_bus.register_hook("tool.call", lambda p: trace.append(("tool.call", p)))
result = await agent.execute("run", {"query": "..."})
# trace now contains every tool call made during the run
```
