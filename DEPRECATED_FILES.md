# Deprecated Files - Unified Event System Migration

The following files have been deprecated as part of the unified event system migration that eliminates threading issues and provides real-time event delivery.

## Replaced Files

### Core System
- `woodwork/core/distributed_startup.py` → Replaced with `woodwork/core/async_runtime.py`
  - **Reason**: Eliminated threading separation and cross-thread communication
  - **New**: Single async runtime for all components

- `woodwork/core/message_bus/declarative_router.py` → Merged into `woodwork/core/unified_event_bus.py`
  - **Reason**: Unified routing with event system
  - **New**: Direct component routing without thread boundaries

- `woodwork/events/events.py` (EventManager) → Replaced with `woodwork/core/unified_event_bus.py`
  - **Reason**: Combined event management with routing
  - **New**: Unified event bus for all communication

### Component Files
- `woodwork/components/inputs/api_input_old.py` → Replaced with `woodwork/components/inputs/api_input.py`
  - **Reason**: Removed cross-thread queues and processors
  - **New**: Direct async WebSocket event delivery

## Migration Status

### Completed ✅
- [x] UnifiedEventBus implementation
- [x] AsyncRuntime implementation
- [x] API input component refactoring
- [x] Component registration system updates

### Deprecated Features Removed ❌
- Cross-thread event queues (`_cross_thread_event_queue`)
- Priority event queues (`_priority_event_queue`)
- Thread-based event processors (`_cross_thread_event_processor`)
- Uvicorn loop capture (`_uvicorn_loop`)
- Message bus threading separation
- Distributed startup threading

### New Architecture Benefits ✅
- Real-time event delivery (< 10ms)
- No thread synchronization overhead
- Single async context for all components
- Container-ready architecture
- Simplified debugging and testing

## Breaking Changes

### For Developers
- Components now run in single async context
- Event handling is fully async
- No more cross-thread communication
- WebSocket events delivered immediately

### For Configuration
- API components no longer need special threading handling
- Event hooks work in real-time
- Simplified deployment configuration

## Rollback Instructions

If rollback is needed:
1. Restore `woodwork/core/distributed_startup.py`
2. Restore `woodwork/core/message_bus/declarative_router.py`
3. Restore `woodwork/components/inputs/api_input_old.py` as `api_input.py`
4. Update imports in affected modules

## Testing

Run the unified event system tests to verify functionality:
```bash
pytest tests/unit/test_unified_event_system.py -v
```

Expected improvements:
- Event delivery < 10ms (was batched/delayed)
- No threading race conditions
- Simplified component lifecycle
- Real-time WebSocket communication