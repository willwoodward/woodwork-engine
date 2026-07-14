# Plan: Remove TaskMaster & Consolidate Message Bus (Phase 6 + TaskMaster removal)

## Task A: Remove TaskMaster

TaskMaster is a legacy orchestrator that duplicates AsyncRuntime. It has two roles:
1. **Component registry** — `_tools` list populated by `add_tools()`
2. **Legacy runtime loop** — `start()` → `_loop()` for input→output routing

**Changes:**
1. **`factory.py`** — Replace `_task_m`/`_get_task_master()`/`_TaskMasterProxy` with a simple `_components` list + `get_components()`/`set_components()`
2. **`parser.py`** — `_get_task_master().add_tools(tools)` → `set_components(tools)`
3. **`operations.py`** — `_get_task_master()._tools` → `get_components()`
4. **`cli/main.py`** — inline a simple `start_cli_runtime()` to replace `_get_task_master().start()`
5. **`gui/gui.py`** — take component list instead of TaskMaster
6. **Delete `runtime/task_master.py`**
7. **Update tests** that mock `_get_task_master`

## Task B: Phase 6 — Consolidate Message Buses

Three message buses exist: `SimpleMessageBus` (raw dicts, simple), `InMemoryMessageBus` (MessageEnvelope objects, complex), and `MessageBusInterface` (abstract base). Redis/NATS backends are stubs.

**Changes:**
1. Keep `SimpleMessageBus` as the one bus, rename to `MessageBus`
2. Delete `message_bus/in_memory_bus.py` and `message_bus/factory.py`
3. Simplify `message_bus/interface.py` — keep MessageEnvelope, drop abstract class
4. Update `integration.py`, `async_runtime.py`, `unified_event_bus.py` to use `MessageBus` directly
5. Update tests
