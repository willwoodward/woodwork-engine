---
title: Component Lifecycle
description: The Component base class, Stoppable interface, and lifecycle contract
index: 2
---

# Component Lifecycle

Every Woodwork component — LLMs, agents, tools, inputs, MCP servers — inherits from `woodwork/components/component.py`.

## The Component Base Class

```python
class Component(Stoppable):
    def __init__(self, name: str, component: str, type: str, **config): ...

    def initialize(self) -> None: ...          # sync, called before start()
    async def start(self) -> None: ...         # async, connect to services
    async def stop(self) -> None: ...          # async, disconnect / close
    def close(self) -> None: ...               # sync alias (backwards compat)

    async def execute(self, action: str, inputs: dict) -> Any: ...
    def _register_hooks_pipes(self, event_bus): ...
```

**All methods have no-op defaults.** Subclasses override only what they need.

## Lifecycle Methods

### `initialize()`

Synchronous. Called before the event loop is hot. Use for things that don't need async: validating config, setting up internal state, pulling an Ollama model.

```python
# OllamaLLM.initialize()
def initialize(self) -> None:
    self._pull_model_if_needed()
    self._client = Ollama(model=self.model)
```

### `start()`

Async. Called once the event loop is running. Use for opening network connections, authenticating, starting background tasks.

```python
# MCPServer.start()
async def start(self) -> None:
    self.metadata = await self.registry.get_server(...)
    self.channel = await self.manager.create_channel(self.metadata, ...)
    self._message_listener_task = asyncio.create_task(self._message_listener())
```

### `stop()`

Async. Guaranteed to run during shutdown. Close sessions, cancel tasks, release resources.

Components that have significant cleanup override `stop()` explicitly. The `Stoppable` interface (`woodwork/interfaces/stoppable.py`) makes this contract explicit:

```python
class Stoppable(ABC):
    @abstractmethod
    async def stop(self) -> None: ...
```

### Order in AsyncRuntime

```
initialize() — in dep order, sequential
start()      — all concurrently (asyncio.gather)
stop()       — all sequentially during cleanup
```

## The execute() API

Tools and agents expose a single entry point:

```python
async def execute(self, action: str, inputs: dict) -> Any
```

`action` is a string describing what to do (e.g. `"run"`, `"search"`, `"call_tool"`). `inputs` is a free-form dict. The return value is whatever the tool produces.

Examples:

```python
# LLMAgent
await agent.execute("run", {"query": "What's on my calendar?", "session_id": "abc"})

# MCPServer (calendar tool)
await calendar.execute("list_events", {"timeMin": "2024-01-01"})

# Functions tool
await calculator.execute("calculate", {"expression": "2 + 2"})
```

The `AgentLoop` calls `ToolRegistry.execute(name, action, inputs)` which dispatches to the right component's `execute()`.

## Hook and Pipe Config

Components read `hooks` and `pipes` arrays from their `.ww` config in `__init__`:

```python
self._hook_configs = self._parse_hooks(config.get("hooks", []))
self._pipe_configs = self._parse_pipes(config.get("pipes", []))
```

These are registered onto the component's EventBus during `start()` via `_register_hooks_pipes(event_bus)`. The function loading is deferred until then (lazy import from the user's script file).

## Adding a New Component

Minimal template:

```python
from woodwork.components.component import Component
from woodwork.utils import format_kwargs

class MyTool(Component):
    def __init__(self, param: str, **config):
        format_kwargs(config, component="my_category", type="my_type")
        super().__init__(**config)
        self.param = param

    async def start(self) -> None:
        # open connections
        pass

    async def stop(self) -> None:
        # close connections
        pass

    async def execute(self, action: str, inputs: dict):
        # do the work
        return result
```

Then add it to `create_object()` in `woodwork/config/factory.py`.
