---
title: AsyncRuntime
description: How the runtime orchestrates component lifecycle and drives the main loop
index: 3
---

# AsyncRuntime

`woodwork/core/runtime.py` — the orchestrator that takes a flat list of components and a dependency map, manages their full lifecycle, runs the main loop, and shuts everything down cleanly.

## Startup Sequence

```python
runtime = AsyncRuntime(system_bus=EventBus())
await runtime.start(components, dep_map)
```

Inside `start()`:

```
1. Register all components in self._components dict
2. _topo_sort(components, dep_map)   → ordered list (deps first)
3. _initialize_all(ordered)          → call initialize() sequentially
4. _start_all(ordered)               → call start() concurrently
5. _main_loop()                      → CLI or API mode
6. finally: _cleanup()               → stop all components
```

### Dependency Sort

`_topo_sort()` is a DFS topological sort. Given:

```ww
assistant = agent llm { model: model, tools: [calendar] }
model = llm claude { ... }
calendar = mcp server { ... }
```

`dep_map` is `{"assistant": ["model", "calendar"], "model": [], "calendar": []}`.

The sort produces `[model, calendar, assistant]` so the LLM and MCP server are initialized before the agent that uses them.

### Concurrent Start

`_start_all()` wraps each async `start()` in a `create_task` and gathers them all:

```python
tasks = [asyncio.create_task(comp.start()) for comp in components if ...]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

Failures are logged but don't abort startup for other components.

## Main Loop Modes

After startup, `_main_loop()` picks a mode:

### CLI Mode (`_run_cli`)

Used when there's a component with a `stream()` method (e.g. `CommandLineInput`).

```python
async for query in input_comp.stream():
    result = await agent_comp.execute("run", {"query": query})
    await input_comp.respond(result)
```

`stream()` is an async generator over stdin using `asyncio.connect_read_pipe` — no blocking threads, so Ctrl+C cancels cleanly.

### API Mode (`_run_api`)

Used when a component has `start_server()` (e.g. `APIInput`). The runtime creates a task for the server and awaits it.

## Shutdown and Cleanup

When Ctrl+C is pressed:

1. The current `await` inside `stream()` receives `CancelledError`
2. `stream()` catches it and returns — the async-for loop exits
3. `_run_cli()` returns, `_main_loop()` returns
4. The `finally` block in `start()` calls `await self._cleanup()`

### The CancelledError Problem

A task being cancelled causes every `await` inside a `finally` block to immediately raise `CancelledError` again — before component cleanup can run.

The fix uses `task.uncancel()` (Python 3.11+):

```python
async def _cleanup(self) -> None:
    task = asyncio.current_task()
    cancelling = task.cancelling() if task is not None else 0
    for _ in range(cancelling):
        task.uncancel()           # pause cancellation

    try:
        for comp in self._components.values():
            await comp.stop()     # awaits work normally now
    finally:
        for _ in range(cancelling):
            task.cancel()         # restore so task terminates correctly
```

`task.uncancel()` decrements the internal cancellation counter; `task.cancel()` restores it. The task still terminates after `_cleanup()` — it just doesn't get prematurely interrupted during cleanup.

## system_bus

`AsyncRuntime` owns a `system_bus: EventBus`. It passes this to `LLMAgent` at construction so each agent's per-agent bus can bubble events up to the system level for cross-agent observability.

Currently the system bus has no listeners attached by default — it's the hook point for external monitoring tools.
