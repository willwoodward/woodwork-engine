# Woodwork Engine — Refactor Plan

## Why

The codebase has grown organically and has tangled three distinct concerns into one system:

- **Execution** — how the agent runs and calls tools
- **Observability** — hooks and pipes watching what happens
- **Deployment** — how components communicate across machines

The result is that every component carries distributed messaging infrastructure it doesn't need, tool calls go through a message bus polling loop instead of direct async calls, and the agent's execution path is impossible to follow without tracing through four layers of indirection.

No backwards compatibility required. We delete what isn't needed and rebuild the core cleanly.

---

## Current Architecture — The Problem

```
┌─────────────────────────────────────────────────────────────────┐
│                      Component (base class)                      │
│               + MessageBusIntegration (mixin)                    │
│   _message_bus  _router  output_targets  session_id  stats       │
└─────────────────────────────┬───────────────────────────────────┘
                              │ inherited by EVERY component
           ┌──────────────────┼──────────────────┐
           ↓                  ↓                  ↓
       LLMAgent           MCPServer        CommandLineInput
           │                  │                  │
           │  self.request()  │                  │
           │  (tool calls go  │                  │
           │   through bus)   │                  │
           └──────────────────┴──────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────────────┐
        │              UnifiedEventBus  (853 lines)            │
        │                                                      │
        │  • Component registry     • Routing inference        │
        │  • Hooks and pipes        • Tool schema registry     │
        │  • Message bus wiring     • Virtual components       │
        └─────────────────────────────┬───────────────────────┘
                                      │
                                      ▼
        ┌─────────────────────────────────────────────────────┐
        │              InMemoryMessageBus                      │
        │                                                      │
        │  • Background retry processor (asyncio task)        │
        │  • Background cleanup processor (asyncio task)      │
        │  • Dead letter queue                                 │
        │  • Component queues                                  │
        │  • 50ms polling loop waiting for tool responses     │
        └─────────────────────────────────────────────────────┘
```

**What a tool call actually does today:**

```
agent.request("calendar", data)
  → router.send_to_component_with_response("calendar", ...)
    → message_bus.send_to_component(envelope)
      → calendar._handle_bus_message(envelope)
        → calendar processes and sends response envelope
          → agent polls _received_responses dict every 50ms
            → timeout if nothing arrives within 5 seconds
```

Six hops, a polling loop, retry queues, and a 5-second timeout to do what should be:

```python
result = await calendar.execute("listEvents", inputs)
```

---

## Target Architecture — The Solution

```
                    ┌─────────────────────────────┐
                    │       Component (base)        │
                    │                              │
                    │  initialize()  start()       │
                    │  stop()        execute()     │
                    └──────────────┬───────────────┘
           ┌──────────────────────┼───────────────────────┐
           ↓                      ↓                       ↓
       LLMAgent               MCPServer           CommandLineInput
     (Component)            (Component+Tool)       (Component)
           │                      │                       │
           │ owns AgentLoop        │                       │
           └──────────┬───────────┘                       │
                      │                                   │
        ┌─────────────▼──────────┐   ┌────────────────────▼──────┐
        │      ToolRegistry      │   │       AsyncRuntime         │
        │                        │   │                            │
        │  register(name, comp)  │   │  topological initialize()  │
        │  execute(name, action) │   │  start() / stop()          │
        │                        │   │  input routing             │
        │  LocalTransport ──────►│   │  system EventBus           │
        │  MCPTransport  ──────►│   └────────────────────────────┘
        └────────────────────────┘

  Per-agent EventBus (scoped)          System EventBus (runtime-owned)
  ┌──────────────────────────┐         ┌──────────────────────────┐
  │  hooks  — concurrent,    │─bubbles─►  hooks only — audit,     │
  │           read-only      │  up to  │  cross-agent logging     │
  │  pipes  — sequential,    │         │                          │
  │           Halt/Retry/    │         │  pipes NOT allowed here  │
  │           Spawn          │         │  (can't intercept across │
  │                          │         │   agents)                │
  └──────────────────────────┘         └──────────────────────────┘
```

**What a tool call does in the new architecture:**

```
await self.tools.execute("calendar", "listEvents", inputs)
  → ToolRegistry looks up "calendar"
    → LocalTransport.call("listEvents", inputs)
      → await calendar.execute("listEvents", inputs)
        → result
```

One hop, direct async call, no polling, no timeout needed.

**Multi-agent: agents are tools too**

```
writer calls researcher:
  await self._tools.execute("researcher", "run", {"query": "...", "session_id": "..."})
    → ToolRegistry looks up "researcher"
      → LocalTransport.call("run", inputs)
        → await researcher.execute("run", inputs)
          → researcher's AgentLoop.run(query, session_id)
            → result
```

No special multi-agent wiring. `researcher` is just another entry in `ToolRegistry`.

---

## Separation of Concerns

```
┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
│     EXECUTION        │   │   OBSERVABILITY      │   │    DEPLOYMENT       │
│                     │   │                      │   │                     │
│  AgentLoop          │   │  EventBus            │   │  MCPTransport       │
│  AgentContext       │   │  hooks (read-only)   │   │  docker-compose     │
│  ToolRegistry       │   │  pipes (transform    │   │  woodwork build     │
│  AsyncRuntime       │   │    + control flow)   │   │                     │
│  Component lifecycle│   │  WorkflowsFeature    │   │  (future)           │
│                     │   │  WorkflowExecutor    │   │  BusTransport       │
└─────────────────────┘   └─────────────────────┘   └─────────────────────┘
       always runs               optional                 deployment only
```

---

## How Pipes Know When to Fire

Pipes are not magic. They fire because `AgentLoop.run()` calls `self._events.emit()` at specific points in the execution path. Here is the complete list of emit points in the loop:

```
query arrives
  → emit("input.received", ...)      # WorkflowsFeature pipe checks for cached workflow
  → LLM called
  → emit("agent.thought", ...)       # pipes can Halt or inject corrections
  → emit("tool.call", ...)           # pipes can Halt, Retry, or Spawn
  → tool executes
  → emit("tool.observation", ...)    # hooks record results
  → emit("agent.step_complete", ...) # WorkflowsFeature hook saves the step
  → loop repeats or exits
```

**Registration flow:**

```
startup:
  feature = WorkflowsFeature(store=neo4j)
  feature.register(agent.event_bus)          # registers on per-agent bus
    → event_bus.register_pipe("input.received", feature._check_similar_workflows)
    → event_bus.register_hook("agent.action", feature._record_action)

runtime:
  runtime.system_bus.register_hook("agent.thought", audit_logger)  # cross-agent logging

execution:
  await event_bus.emit("agent.thought", payload, context)
    → runs all hooks concurrently (per-agent + bubbles to system)
    → runs each pipe sequentially until Halt/Retry/Spawn or end
    → returns modified payload or directive
```

**Why per-agent EventBus, not global?**

If a pipe is registered globally, it can intercept events from agents it has no business modifying. A loop-detection pipe on the `researcher` agent should not fire for the `writer` agent. Scoping to the agent means pipes are isolated — the feature registers on one bus and can't accidentally affect other agents.

System bus hooks are read-only (no pipes allowed) so observability tools can watch all agents safely without the ability to interfere.

---

## What Gets Deleted

No mercy. These are removed entirely:

```
woodwork/runtime/message_bus/          — entire directory
woodwork/runtime/unified_event_bus.py  — replaced by core/events.py (~100 lines)
woodwork/runtime/async_runtime.py      — replaced by core/runtime.py
woodwork/core/task_master.py           — superseded by WorkflowsFeature
woodwork/runtime/                      — entire directory (replaced by core/)

Within components:
  components/component.py              — gutted, MessageBusIntegration removed
  components/internal_features/base.py — InternalComponentManager deleted
  components/agents/llm.py             — hasattr(_task_m) dead code removed
                                         current_prompt string replaced by AgentContext
                                         self.request() replaced by ToolRegistry
```

---

## What Gets Kept (and ported)

These work. They just need to fit the new base class.

```
woodwork/components/mcp/           — MCP protocol logic is sound, keep it
woodwork/components/llms/          — all four LLM integrations
woodwork/components/apis/          — function and OpenAPI tools
woodwork/components/knowledge_bases/ — Neo4j, Chroma
woodwork/components/inputs/        — CLI, API, voice
woodwork/components/outputs/       — voice, console
woodwork/config/                   — parser, tokenizer, resolver (unchanged)
woodwork/types/                    — event payload types (keep as-is)
woodwork/components/internal_features/workflows.py — logic is right, clean it up
```

---

## New Directory Structure

```
woodwork/
  core/
    types.py          — AgentContext, Step, Message (NEW)
    protocols.py      — Component, Transport, WorkflowStore, Startable (NEW)
    directives.py     — Halt, Retry, Spawn pipe return types (NEW)
    events.py         — EventBus, hooks, pipes (NEW, replaces unified_event_bus)
    tools.py          — ToolRegistry, LocalTransport, MCPTransport (NEW)
    runtime.py        — AsyncRuntime, system EventBus, multi-agent (NEW)

  components/
    component.py      — clean base class, no MessageBusIntegration
    agents/
      agent_loop.py   — AgentLoop: pure LLM execution logic (NEW)
      llm.py          — LLMAgent(Component): wraps AgentLoop, implements execute()
    llms/             — ported as-is
    mcp/              — ported as-is
    apis/             — ported as-is
    inputs/           — ported
    outputs/          — ported
    knowledge_bases/  — ported
    internal_features/
      workflows.py    — cleaned up
      stores/
        neo4j_store.py — WorkflowStore implementation

  config/             — unchanged
  types/              — unchanged
  features/
    workflow_executor.py — uses ToolRegistry directly
```

---

## Day 1 — Contracts and Types

**Goal:** Define what everything is before building anything. If you can't write these cleanly, the design isn't clear enough.

### Create `woodwork/core/types.py`

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass
class Message:
    role: str        # "user" | "assistant"
    content: str

@dataclass
class Step:
    thought: str
    tool: str
    action: str
    inputs: dict[str, Any]
    observation: str
    output_var: str

@dataclass
class AgentContext:
    session_id: str
    query: str
    steps: list[Step] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)
    iteration: int = 0

    def to_prompt(self) -> str:
        if not self.steps:
            return ""
        return "\n\n".join(
            f"Thought: {s.thought}\n"
            f"Action: {{\"tool\": \"{s.tool}\", \"action\": \"{s.action}\", "
            f"\"inputs\": {s.inputs}, \"output\": \"{s.output_var}\"}}\n"
            f"Observation: {s.observation}"
            for s in self.steps
        )
```

### Create `woodwork/core/protocols.py`

```python
from typing import Any, Protocol, runtime_checkable

@runtime_checkable
class Startable(Protocol):
    async def initialize(self) -> None: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...

@runtime_checkable
class Tool(Protocol):
    name: str
    async def execute(self, action: str, inputs: dict[str, Any]) -> Any: ...

@runtime_checkable
class Transport(Protocol):
    async def call(self, action: str, inputs: dict[str, Any]) -> Any: ...

@runtime_checkable
class WorkflowStore(Protocol):
    async def save(self, session_id: str, query: str, steps: list) -> str: ...
    async def find_similar(self, query: str, threshold: float) -> list: ...
    async def get(self, workflow_id: str) -> list: ...
```

### Create `woodwork/core/directives.py`

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class Halt:
    """Stop execution and return this reason."""
    reason: str

@dataclass
class Retry:
    """Rewind context to this step and re-execute."""
    from_step: int
    inject: str = ""

@dataclass
class Spawn:
    """Run this callable before continuing."""
    target: Any
    inputs: dict[str, Any]
```

**Tests to write:** Instantiate each type, verify `to_prompt()` renders correctly for zero and multiple steps.

**Delete:** Nothing yet.

---

## Day 2 — EventBus

**Goal:** Replace `UnifiedEventBus` (853 lines doing too many things) with a focused event bus that handles only hooks and pipes.

### Delete

```
woodwork/runtime/unified_event_bus.py
```

### Create `woodwork/core/events.py`

```python
import asyncio
import logging
from typing import Any, Callable
from .types import AgentContext
from .directives import Halt, Retry, Spawn

log = logging.getLogger(__name__)

PipeResult = Any  # Payload | Halt | Retry | Spawn

class EventBus:
    def __init__(self, parent: "EventBus | None" = None):
        self._hooks: dict[str, list[Callable]] = {}
        self._pipes: dict[str, list[Callable]] = {}
        self._parent = parent  # system bus, receives bubbled hooks only

    def register_hook(self, event: str, fn: Callable) -> None:
        self._hooks.setdefault(event, []).append(fn)

    def register_pipe(self, event: str, fn: Callable) -> None:
        self._pipes.setdefault(event, []).append(fn)

    async def emit(self, event: str, payload: Any, context: AgentContext) -> PipeResult:
        # Run local hooks concurrently — read-only, fire and forget
        await self._run_hooks(event, payload, context)

        # Bubble to parent (system bus) — hooks only, no pipes
        if self._parent:
            await self._parent._run_hooks(event, payload, context)

        # Run pipes sequentially — can transform payload or return a directive
        for pipe in self._pipes.get(event, []):
            result = await self._run_pipe(pipe, payload, context)
            if isinstance(result, (Halt, Retry, Spawn)):
                return result
            if result is not None:
                payload = result

        return payload

    async def _run_hooks(self, event: str, payload: Any, context: AgentContext) -> None:
        hooks = self._hooks.get(event, [])
        if hooks:
            await asyncio.gather(
                *[self._run_hook(fn, payload, context) for fn in hooks],
                return_exceptions=True
            )

    async def _run_hook(self, fn, payload, context):
        try:
            if asyncio.iscoroutinefunction(fn):
                await fn(payload, context)
            else:
                fn(payload, context)
        except Exception:
            log.exception(f"Hook {fn.__name__} raised an exception")

    async def _run_pipe(self, fn, payload, context):
        try:
            if asyncio.iscoroutinefunction(fn):
                return await fn(payload, context)
            return fn(payload, context)
        except Exception:
            log.exception(f"Pipe {fn.__name__} raised an exception")
            return payload
```

**Tests to write:**
- Hook fires and receives payload + context
- Pipe transforms payload
- Pipe returning `Halt` stops further processing
- Multiple hooks run concurrently (use timing)
- Exception in hook doesn't crash the bus
- Child bus bubbles hooks to parent but NOT pipes
- Parent hook fires even when child has no hooks registered for that event

---

## Day 3 — ToolRegistry

**Goal:** Single interface for calling tools regardless of where they live.

### Create `woodwork/core/tools.py`

```python
import logging
from typing import Any
from .protocols import Tool, Transport

log = logging.getLogger(__name__)


class LocalTransport:
    """Calls the component directly in-process."""
    def __init__(self, component: Tool):
        self._component = component

    async def call(self, action: str, inputs: dict[str, Any]) -> Any:
        return await self._component.execute(action, inputs)


class MCPTransport:
    """Calls a remote MCP server over HTTP/SSE. Implemented on Day 8."""
    def __init__(self, url: str):
        self._url = url

    async def call(self, action: str, inputs: dict[str, Any]) -> Any:
        raise NotImplementedError("MCPTransport implemented in Day 8")


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Transport] = {}

    def register(self, name: str, transport: Transport) -> None:
        self._tools[name] = transport
        log.debug(f"Registered tool: {name} ({type(transport).__name__})")

    def register_local(self, component: Tool) -> None:
        self.register(component.name, LocalTransport(component))

    async def execute(self, tool_name: str, action: str, inputs: dict[str, Any]) -> Any:
        if tool_name not in self._tools:
            raise KeyError(f"Tool '{tool_name}' not registered. Available: {list(self._tools)}")
        return await self._tools[tool_name].call(action, inputs)

    @property
    def available_tools(self) -> list[str]:
        return list(self._tools.keys())
```

**Tests to write:**
- Register a mock tool and call it
- `execute` raises `KeyError` for unknown tool
- `LocalTransport` calls `component.execute` with correct args

---

## Day 4 — AgentLoop

**Goal:** Clean, readable execution loop. The whole thing should be understandable in one read.

`AgentLoop` lives in `components/agents/` because it's only ever used by agent components — it's not a cross-cutting primitive like `ToolRegistry` or `EventBus`. `LLMAgent` (the Component wrapper) and `AgentLoop` (the execution logic) sit side by side in the same package.

### Create `woodwork/components/agents/agent_loop.py`

```python
import json
import logging
import re
from typing import Any
from woodwork.core.types import AgentContext, Step
from woodwork.core.events import EventBus
from woodwork.core.tools import ToolRegistry
from woodwork.core.directives import Halt, Retry, Spawn
from woodwork.types.events import (
    AgentThoughtPayload, ToolCallPayload, ToolObservationPayload,
    AgentStepCompletePayload, AgentErrorPayload
)

log = logging.getLogger(__name__)


class AgentLoop:
    def __init__(
        self,
        name: str,
        llm,
        tool_registry: ToolRegistry,
        event_bus: EventBus,
        system_prompt: str,
        max_iterations: int = 10,
    ):
        self.name = name
        self._llm = llm
        self._tools = tool_registry
        self._events = event_bus
        self._system_prompt = system_prompt
        self._max_iterations = max_iterations

    async def run(self, query: str, session_id: str) -> str:
        context = AgentContext(session_id=session_id, query=query)

        for i in range(self._max_iterations):
            context.iteration = i

            # Call LLM
            response = await self._llm.call(self._system_prompt, context.to_prompt(), query)
            thought, action, is_final = self._parse(response)

            # Emit thought — pipes can inject corrections or halt
            directive = await self._events.emit(
                "agent.thought",
                AgentThoughtPayload(thought=thought, session_id=session_id),
                context
            )
            if isinstance(directive, Halt):
                return directive.reason

            if is_final:
                await self._events.emit(
                    "agent.step_complete",
                    AgentStepCompletePayload(step=i, session_id=session_id),
                    context
                )
                return thought

            # Emit tool call — pipes can halt, retry, or modify
            directive = await self._events.emit(
                "tool.call",
                ToolCallPayload(tool=action["tool"], action=action["action"],
                                inputs=action["inputs"], session_id=session_id),
                context
            )
            if isinstance(directive, Halt):
                return directive.reason
            if isinstance(directive, Retry):
                context.steps = context.steps[:directive.from_step]
                if directive.inject:
                    context.variables["_injected"] = directive.inject
                continue
            if isinstance(directive, Spawn):
                result = await directive.target(directive.inputs, context)
                observation = str(result)
            else:
                # Execute tool
                try:
                    result = await self._tools.execute(
                        action["tool"], action["action"], action["inputs"]
                    )
                    observation = str(result)
                except Exception as e:
                    await self._events.emit(
                        "agent.error",
                        AgentErrorPayload(error=str(e), session_id=session_id),
                        context
                    )
                    observation = f"Error: {e}"

            await self._events.emit(
                "tool.observation",
                ToolObservationPayload(observation=observation, session_id=session_id),
                context
            )

            context.steps.append(Step(
                thought=thought,
                tool=action["tool"],
                action=action["action"],
                inputs=action["inputs"],
                observation=observation,
                output_var=action.get("output", "result"),
            ))
            context.variables[action.get("output", "result")] = result

        return "Max iterations reached without a final answer."

    def _parse(self, response: str) -> tuple[str, dict | None, bool]:
        """Extract thought, action, and whether this is a final answer."""
        thought_match = re.search(r"Thought:\s*(.+?)(?=\nAction:|\nFinal Answer:|$)", response, re.DOTALL)
        thought = thought_match.group(1).strip() if thought_match else response.strip()

        if "Final Answer:" in response:
            return thought, None, True

        action_match = re.search(r"Action:\s*(\{.+?\})", response, re.DOTALL)
        if action_match:
            try:
                action = json.loads(action_match.group(1))
                return thought, action, False
            except json.JSONDecodeError:
                pass

        return thought, None, True
```

**Tests to write:**
- `_parse` extracts thought and action correctly
- `_parse` detects Final Answer
- Pipe returning `Halt` stops the loop
- Pipe returning `Retry` rewinds steps
- Tool error is caught and added to observation
- Max iterations returns sensible string

---

## Day 5 — AsyncRuntime

**Goal:** Clean lifecycle orchestration. Starts components in the right order, runs the input loop, shuts down cleanly.

### Delete

```
woodwork/runtime/async_runtime.py
woodwork/runtime/  (entire directory once message_bus also gone)
```

### Create `woodwork/core/runtime.py`

The runtime owns the **system EventBus** and creates a **per-agent EventBus** for each `LLMAgent`. It routes incoming queries to the correct agent based on component configuration.

```python
import asyncio
import logging
from typing import Any
from .protocols import Tool
from .tools import ToolRegistry
from .events import EventBus

log = logging.getLogger(__name__)


def topological_sort(components: list, dependencies: dict[str, list[str]]) -> list:
    """Sort components so dependencies initialize before dependents."""
    visited = set()
    result = []

    def visit(name: str):
        if name in visited:
            return
        visited.add(name)
        for dep in dependencies.get(name, []):
            visit(dep)
        comp = next((c for c in components if c.name == name), None)
        if comp:
            result.append(comp)

    for component in components:
        visit(component.name)

    return result


class AsyncRuntime:
    def __init__(self):
        self._components: list = []
        self._dependencies: dict[str, list[str]] = {}
        self._tool_registry = ToolRegistry()
        self.system_bus = EventBus()          # cross-agent observability, hooks only
        self._agents: dict[str, Any] = {}     # name → LLMAgent
        self._input_component = None
        self._default_agent: str | None = None

    def add_component(self, component, dependencies: list[str] | None = None) -> None:
        self._components.append(component)
        if dependencies:
            self._dependencies[component.name] = dependencies

    def set_input(self, component) -> None:
        self._input_component = component

    async def start(self) -> None:
        ordered = topological_sort(self._components, self._dependencies)

        # Initialize in dependency order
        for component in ordered:
            log.info(f"Initializing {component.name}")
            await component.initialize()

        # Register tools and agents
        for component in self._components:
            if isinstance(component, Tool):
                self._tool_registry.register_local(component)
                log.debug(f"Registered tool: {component.name}")

        # Collect agent components (LLMAgent is a Tool too — agents can call each other)
        from woodwork.components.agents.llm import LLMAgent  # avoids circular import at module level
        for component in self._components:
            if isinstance(component, LLMAgent):
                self._agents[component.name] = component
                if self._default_agent is None:
                    self._default_agent = component.name

        # Start all components
        for component in ordered:
            log.info(f"Starting {component.name}")
            await component.start()

        # Run input loop
        if self._input_component:
            await self._run_input_loop()

    async def stop(self) -> None:
        ordered = topological_sort(self._components, self._dependencies)
        for component in reversed(ordered):
            log.info(f"Stopping {component.name}")
            try:
                await component.stop()
            except Exception:
                log.exception(f"Error stopping {component.name}")

    async def _run_input_loop(self) -> None:
        """
        Route incoming queries to the right agent.

        By default, queries go to the first declared agent.
        Input components can specify a target via 'to: agent_name' in config,
        or the input itself can be prefixed with '@agent_name: query'.
        """
        log.info("Runtime ready. Waiting for input.")
        async for query, session_id in self._input_component.stream():
            agent_name, query = self._parse_target(query)
            agent = self._agents.get(agent_name or self._default_agent)
            if agent:
                result = await agent.execute("run", {"query": query, "session_id": session_id})
                await self._input_component.respond(result, session_id)
            else:
                log.warning(f"No agent found for target '{agent_name}'")

    def _parse_target(self, query: str) -> tuple[str | None, str]:
        """Parse '@agent_name: query' prefix if present."""
        if query.startswith("@") and ":" in query:
            name, _, rest = query[1:].partition(":")
            return name.strip(), rest.strip()
        return None, query
```

**Tests to write:**
- `topological_sort` orders correctly given dependencies
- `start()` calls `initialize()` before `start()` on each component
- `stop()` is called in reverse order
- Tools are registered in `ToolRegistry` after `initialize()`
- `_parse_target` extracts agent name and query from `@name: query` prefix
- Multiple agents registered; query routes to correct one

---

## Day 5b — Agent as Component

**Goal:** `LLMAgent` lives in `components/agents/llm.py`, not in `core/`. `AgentLoop` is pure execution logic. `LLMAgent` wraps it in a `Component` and exposes `execute()` so agents can be used as tools for other agents.

This is the boundary that makes multi-agent clean:

```
components/agents/agent_loop.py  — pure execution: LLM call, parse, tool dispatch, emit
                                    knows nothing about Component lifecycle or the runtime
components/agents/llm.py         — LLMAgent(Component): wires AgentLoop, per-agent EventBus,
                                    exposes execute() so agents can be used as tools
```

### Create `woodwork/components/agents/llm.py`

```python
from woodwork.components.agents.agent_loop import AgentLoop
from woodwork.core.events import EventBus
from woodwork.core.tools import ToolRegistry
from woodwork.components.component import Component
from typing import Any


class LLMAgent(Component):
    """
    Component wrapper around AgentLoop.

    - Owns a per-agent EventBus (scoped to this agent)
    - Per-agent bus bubbles hooks to the runtime's system bus
    - Implements execute() so other agents can call this agent via ToolRegistry
    """

    def __init__(self, name: str, config: dict, system_bus: EventBus):
        super().__init__(name, config)
        # Per-agent bus: pipes are scoped here, hooks bubble to system_bus
        self.event_bus = EventBus(parent=system_bus)
        self._loop: AgentLoop | None = None

    async def initialize(self) -> None:
        """Wire up AgentLoop with the per-agent EventBus and ToolRegistry."""
        llm = self.config["llm"]          # resolved LLM component
        tools = self.config["tools"]      # ToolRegistry built by runtime
        system_prompt = self.config.get("system_prompt", "")
        max_iterations = self.config.get("max_iterations", 10)

        self._loop = AgentLoop(
            name=self.name,
            llm=llm,
            tool_registry=tools,
            event_bus=self.event_bus,
            system_prompt=system_prompt,
            max_iterations=max_iterations,
        )

    async def execute(self, action: str, inputs: dict[str, Any]) -> Any:
        """
        Called by ToolRegistry when another agent uses this agent as a tool.

        action: "run"
        inputs: {"query": "...", "session_id": "..."}
        """
        if action != "run":
            raise ValueError(f"LLMAgent only supports action 'run', got '{action}'")
        return await self._loop.run(
            query=inputs["query"],
            session_id=inputs.get("session_id", "default"),
        )
```

**How multi-agent works:**

```python
# In .ww config or Python API:
researcher = LLMAgent(name="researcher", tools=[calendar, email], ...)
writer = LLMAgent(name="writer", tools=[researcher, docs], ...)

# writer's ToolRegistry has researcher registered as a LocalTransport
# when writer calls: await self._tools.execute("researcher", "run", {"query": "..."})
# it calls: researcher.execute("run", {"query": "..."})
# which calls: researcher._loop.run("...")
# researcher runs its own full AgentLoop, returns a string
# writer sees the string as a tool observation
```

Each agent has its own `event_bus`. WorkflowsFeature pipes registered on `researcher.event_bus` cannot fire when `writer` is thinking. The system bus sees both.

**Tests to write:**
- `LLMAgent.initialize()` creates an `AgentLoop` with the correct bus
- `LLMAgent.execute("run", {...})` delegates to `AgentLoop.run()`
- Per-agent EventBus has `system_bus` as parent
- Registering a pipe on one agent's bus does not fire for another agent's events

---

## Day 6 — Component Base Class + LLMs

**Goal:** Strip `MessageBusIntegration` entirely. Port all four LLMs to the clean base class.

### Rewrite `woodwork/components/component.py`

```python
from typing import Any
import logging

log = logging.getLogger(__name__)


class Component:
    """Base class for all Woodwork components."""

    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config

    async def initialize(self) -> None:
        """One-time setup. Establish connections, validate config."""
        pass

    async def start(self) -> None:
        """Begin accepting work."""
        pass

    async def stop(self) -> None:
        """Graceful shutdown."""
        pass

    async def execute(self, action: str, inputs: dict[str, Any]) -> Any:
        """Execute a tool action. Override in tool components."""
        raise NotImplementedError(f"{self.__class__.__name__} does not implement execute()")
```

### Port each LLM

For each of `openai.py`, `claude.py`, `ollama.py`, `hugging_face.py`:

1. Change base class to `Component`
2. Remove all `MessageBusIntegration` references
3. Move connection/client setup into `initialize()`
4. `execute("call", {"messages": [...]})` calls the LLM
5. Keep streaming logic if present

**Example signature after porting:**

```python
class OpenAI(Component):
    async def initialize(self) -> None:
        self._client = openai.AsyncOpenAI(api_key=self.config["api_key"])

    async def call(self, system_prompt: str, context: str, query: str) -> str:
        # called directly by AgentLoop, not through ToolRegistry
        ...
```

LLMs are not tools — they're called directly by `AgentLoop`. They don't go through `ToolRegistry`.

**Delete:**
- All `hasattr(self, "_task_m")` checks in `llm.py`
- `current_prompt` string accumulation (replaced by `AgentContext.to_prompt()`)
- `self.request()` calls (replaced by `ToolRegistry.execute()`)
- `_workflow_variables` dict (replaced by `AgentContext.variables`)
- `_internal_features` and `InternalComponentManager` wiring
- `_pending_user_requests` (human-in-the-loop will be reimplemented as a pipe directive)

**Tests:** Each LLM `initialize()` with a mocked client. Verify `call()` returns a string.

---

## Day 7 — APIs, Inputs, Outputs

**Goal:** Port the tool components and input/output components.

### `woodwork/components/apis/`

Each tool component gets:
- `Component` base class
- `initialize()` for any setup (loading function files, validating OpenAPI spec)
- `execute(action, inputs)` that dispatches to the right function

```python
class FunctionsAPI(Component):
    async def initialize(self) -> None:
        self._functions = self._load_functions(self.config["path"])

    async def execute(self, action: str, inputs: dict) -> Any:
        fn = self._functions.get(action)
        if not fn:
            raise ValueError(f"Function '{action}' not found")
        return await fn(**inputs) if asyncio.iscoroutinefunction(fn) else fn(**inputs)
```

### `woodwork/components/inputs/`

Input components stream queries to the runtime. They implement a `stream()` async generator and a `respond()` method.

```python
class CommandLineInput(Component):
    async def stream(self):
        session_id = str(uuid.uuid4())
        while True:
            query = await asyncio.get_event_loop().run_in_executor(None, input, "\n> ")
            if query.lower() in ("exit", "quit"):
                break
            yield query, session_id

    async def respond(self, result: str, session_id: str) -> None:
        print(f"\n{result}")
```

**Delete from inputs:** All `MessageBusIntegration` routing logic, `output_targets`, `_auto_route_output`.

### `woodwork/components/outputs/`

Outputs become simple callables registered as hooks:

```python
class ConsoleOutput(Component):
    async def write(self, text: str) -> None:
        print(text)
```

**Tests:** Mock `input()` for CLI input test. Verify `stream()` yields (query, session_id) tuples.

---

## Day 8 — MCP Servers

**Goal:** Port MCP servers to the new base class. The protocol logic stays largely unchanged — it's the glue that needs cleaning.

### What changes in `woodwork/components/mcp/mcp_server.py`

1. Base class → `Component`
2. `initialize()` does the protocol handshake and tool discovery (it already does this, just move it)
3. `execute(action, inputs)` calls the tool via the existing channel (already exists as `call_tool()`)
4. Remove all `MessageBusIntegration` references
5. Remove routing and `output_targets`

```python
class MCPServer(Component):
    async def initialize(self) -> None:
        await self._start_server_process()
        await self._handshake()
        self._tools = await self._discover_tools()
        log.info(f"MCP server {self.name} ready with tools: {list(self._tools)}")

    async def execute(self, action: str, inputs: dict) -> Any:
        return await self._call_tool(action, inputs)

    async def stop(self) -> None:
        await self._shutdown_server()
```

### Implement `MCPTransport` in `woodwork/core/tools.py`

For remote MCP servers in Docker containers:

```python
class MCPTransport:
    """HTTP/SSE transport for remote MCP servers."""
    def __init__(self, url: str):
        self._url = url
        self._session = None

    async def initialize(self) -> None:
        import aiohttp
        self._session = aiohttp.ClientSession()
        await self._discover_tools()

    async def call(self, action: str, inputs: dict) -> Any:
        async with self._session.post(
            f"{self._url}/tools/call",
            json={"name": action, "arguments": inputs}
        ) as resp:
            return await resp.json()
```

**Tests:** Mock the MCP channel. Verify `initialize()` calls `_discover_tools()`. Verify `execute()` calls `_call_tool()`.

---

## Day 9 — Parser + Internal Features

**Goal:** Parser factory calls the new Python API. WorkflowsFeature and WorkflowExecutor cleaned up and using new interfaces.

### `woodwork/config/factory.py`

The parser (tokenizer, config_parser, resolver) is **unchanged**. Only the factory changes.

**Before:** Factory calls `InternalComponentManager`, wires `MessageBusIntegration`, sets up routing.

**After:** Factory creates components, returns a flat list. Runtime handles wiring.

```python
def build_components(declarations: list[ComponentDeclaration]) -> tuple[list, dict]:
    """
    Returns (components, dependencies).
    Runtime handles initialization order and tool registration.
    """
    components = []
    dependencies = {}

    for decl in declarations:
        component = _create_component(decl)
        components.append(component)
        if decl.dependencies:
            dependencies[decl.name] = [d.name for d in decl.dependencies]

    return components, dependencies
```

### `woodwork/components/internal_features/`

**Delete:**
- `base.py` → `InternalComponentManager` is gone. Neo4j is just passed in directly.

**Keep and clean `workflows.py`:**

```python
class WorkflowsFeature:
    """
    Optional workflow recording and retrieval.
    Registers hooks and pipes on the EventBus.
    Does not modify AgentLoop or any component internals.
    """
    def __init__(self, store: WorkflowStore):
        self._store = store

    def register(self, event_bus: EventBus) -> None:
        event_bus.register_pipe("input.received", self._check_similar_workflows)
        event_bus.register_hook("agent.action", self._record_action)
        event_bus.register_hook("agent.step_complete", self._save_workflow)
```

### Create `woodwork/features/workflow_executor.py`

```python
class WorkflowExecutor:
    def __init__(self, store: WorkflowStore, tools: ToolRegistry):
        self._store = store
        self._tools = tools

    async def replay(self, workflow_id: str, inputs: dict) -> dict:
        steps = await self._store.get(workflow_id)
        variables = inputs.copy()
        for step in steps:
            resolved = {
                k: variables.get(v, v) if isinstance(v, str) else v
                for k, v in step["inputs"].items()
            }
            result = await self._tools.execute(step["tool"], step["action"], resolved)
            variables[step["output"]] = result
        return variables
```

### Create `woodwork/features/stores/neo4j_store.py`

Implements `WorkflowStore` protocol. Extracts the Neo4j query logic from `WorkflowsFeature` into its own class. Anyone can implement a different store.

**Tests:**
- `WorkflowExecutor.replay()` with a mock store and mock tool registry
- `WorkflowsFeature.register()` registers the right events on the bus
- Parser factory returns correct component list and dependency map

---

## Day 10 — Delete Everything Old, Verify

**Goal:** Remove all dead code. Run the full test suite. Confirm nothing references deleted files.

### Deletions (in order)

```bash
# Old runtime
rm -rf woodwork/runtime/message_bus/
rm woodwork/runtime/unified_event_bus.py
rm woodwork/runtime/async_runtime.py
rmdir woodwork/runtime/  # if empty

# Old orchestration
rm woodwork/core/task_master.py

# Internal component manager
# (base.py already cleaned on Day 9, delete what remains)
rm woodwork/components/internal_features/base.py  # if InternalComponentManager is fully gone
```

### Grep for dead references

```bash
# These should return nothing after deletion
grep -r "MessageBusIntegration" woodwork/
grep -r "task_master\|TaskMaster\|_task_m" woodwork/
grep -r "unified_event_bus" woodwork/
grep -r "InternalComponentManager" woodwork/
grep -r "get_global_message_bus\|InMemoryMessageBus" woodwork/
grep -r "self\.request(" woodwork/components/
grep -r "output_targets\|_auto_route" woodwork/
```

All should return empty.

### Update imports

```bash
# Find anything still importing from old locations
grep -r "from woodwork.runtime" woodwork/
grep -r "from woodwork.core.task_master" woodwork/
```

Fix any remaining references to point to `woodwork.core.*`.

### Run the full test suite

```bash
pytest -v
```

Expected failures at this point: tests that specifically tested message bus behaviour (routing, retry, dead letter queue). These tests should be deleted — they were testing deployment infrastructure that no longer lives in the execution layer.

### Update `pyproject.toml`

Remove dependencies that are no longer needed once the message bus infrastructure is gone (if any were added specifically for it).

### Smoke test with `examples/01-getting-started/`

Run the simplest example end-to-end. If this works, the refactor is done.

---

## Definition of Done

After Day 10, the codebase should satisfy all of these:

**Dead code gone:**
- [ ] `grep -r "MessageBusIntegration" woodwork/` returns nothing
- [ ] `grep -r "_task_m\|TaskMaster" woodwork/` returns nothing
- [ ] `grep -r "self\.request(" woodwork/components/` returns nothing
- [ ] `grep -r "polling\|_received_responses\|_wait_for_response" woodwork/` returns nothing
- [ ] `grep -r "unified_event_bus\|InternalComponentManager\|InMemoryMessageBus" woodwork/` returns nothing

**Architecture correct:**
- [ ] `components/agents/agent_loop.py` is readable top to bottom without tracing into other files
- [ ] A tool call from the agent to a component is a single `await` call with no polling
- [ ] `AgentLoop` has zero imports from `woodwork.components` (it's pure logic)
- [ ] `LLMAgent` lives in `components/agents/llm.py` and implements `execute()`
- [ ] Per-agent `EventBus` is created in `LLMAgent.initialize()` with `parent=runtime.system_bus`
- [ ] `WorkflowsFeature` can be removed from a config without touching any other code
- [ ] Registering a pipe on `researcher.event_bus` does not fire when `writer` emits an event
- [ ] `researcher` agent can be called by `writer` agent via `ToolRegistry` with no special wiring

**Tests pass:**
- [ ] Full test suite passes (minus deleted message bus tests)
- [ ] `examples/01-getting-started/` runs successfully
- [ ] `examples/life-assistant/` runs successfully
