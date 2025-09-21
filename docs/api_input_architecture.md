# API Input Component Architecture

## Current Threading Model

### Thread Separation
- **Distributed Startup Thread**: Runs components, LLM agents, emits events via `emit()`
- **Uvicorn Thread**: Runs FastAPI/WebSocket server, handles WebSocket connections
- **Cross-thread Communication**: Queue-based event processor bridges threads

### Event Flow
```
LLM Agent (Startup Thread) → emit() → Event Hooks → Cross-thread Queue → Uvicorn Thread → WebSocket
```

## Key Components

### API Input Component (`api_input.py`)
- **WebSocket Management**: Session tracking with subscription filtering
- **Message Bus Integration**: Receives input via `handle_message()`, sends via `request()`
- **Event Processing**: Hooks into event system for real-time streaming
- **Cross-thread Processor**: `_cross_thread_event_processor()` transfers events between threads

### Event System Integration
- **Event Hooks**: Register for `agent.thought`, `agent.action`, `tool.call`, etc.
- **Priority Handling**: Special queue for `input.received` events
- **Thread Detection**: Attempts immediate delivery when on uvicorn thread

## Threading Issues

### Root Problem
Event emission (`emit()`) happens in distributed startup thread, but WebSocket delivery requires uvicorn thread context. Current queue-based approach introduces batching delays.

### Current Workarounds
1. Cross-thread event queue with asyncio bridge
2. Priority queue for time-sensitive events
3. Thread detection for immediate delivery attempts
4. `time.sleep(0.001)` delays in LLM component for event processing

## Simplification Opportunities

### Thread Consolidation
- Move component execution to uvicorn thread or shared async context
- Eliminate cross-thread queuing mechanism
- Direct event delivery without thread boundaries

### Event System Unification
- Align `emit()` system with message bus for consistent delivery
- Remove duplicate communication paths
- Simplify event routing architecture

### WebSocket Integration
- Direct event subscription without intermediate queuing
- Unified session management across all component types
- Real-time delivery guarantee through thread alignment

## Technical Debt
- Dual communication systems (emit + message bus)
- Complex cross-thread synchronization
- Multiple event processing delays
- Thread-dependent delivery mechanisms