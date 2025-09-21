# Unified Event & Component Architecture Solution

## Test-Driven Design Goals

### Test Requirements
```python
def test_unified_real_time_delivery():
    """Events must be delivered in real-time without thread delays"""

def test_single_communication_system():
    """All component communication uses unified event system"""

def test_container_ready_architecture():
    """Components can run in separate containers with message passing"""

def test_direct_event_routing():
    """No intermediate queues between event emission and delivery"""
```

## Unified Architecture

### 1. Consolidated Event System
**Replace**: EventManager + DeclarativeRouter + MessageBus
**With**: `UnifiedEventBus`

```python
class UnifiedEventBus:
    """Single event system for all component communication"""

    async def emit(self, event_type: str, payload: BasePayload) -> None:
        """Unified emission - handles routing, hooks, and inter-component messages"""

    async def route_to_component(self, target: str, payload: BasePayload) -> None:
        """Direct component routing without thread boundaries"""

    def register_component(self, component: Component) -> None:
        """Register component for event delivery"""
```

### 2. Async Component Runtime
**Replace**: Distributed startup thread separation
**With**: Single async runtime

```python
class AsyncComponentRuntime:
    """All components run in unified async context"""

    async def start_component(self, component: Component) -> None:
        """Start component in async context"""

    async def handle_component_input(self, component: Component, input_data: Any) -> Any:
        """Direct async component invocation"""
```

### 3. Container-First Messaging
**Design for**: Each component in own container
**Communication**: Direct async message passing

```python
class ContainerBridge:
    """Bridge for containerized component communication"""

    async def send_to_container(self, container_id: str, event: BasePayload) -> None:
        """Send event to component container"""

    async def receive_from_container(self) -> BasePayload:
        """Receive events from component containers"""
```

## Migration Strategy

### Phase 1: Unify Event Systems
```python
# Delete: woodwork/core/message_bus/declarative_router.py
# Delete: woodwork/events/events.py (EventManager)
# Create: woodwork/core/unified_event_bus.py

class UnifiedEventBus:
    def __init__(self):
        self._components: Dict[str, Component] = {}
        self._routing_table: Dict[str, List[str]] = {}
        self._event_hooks: Dict[str, List[Callable]] = {}

    async def emit(self, event_type: str, payload: BasePayload) -> BasePayload:
        # 1. Process hooks (concurrent)
        await self._process_hooks(event_type, payload)

        # 2. Route to target components (direct async calls)
        await self._route_to_components(event_type, payload)

        return payload
```

### Phase 2: Async Runtime Consolidation
```python
# Replace: woodwork/core/distributed_startup.py
# With: woodwork/core/async_runtime.py

class AsyncRuntime:
    def __init__(self):
        self.event_bus = UnifiedEventBus()
        self.components: Dict[str, Component] = {}

    async def start(self, config: Dict[str, Any]) -> None:
        # 1. Parse components
        components = parse_components(config)

        # 2. Register with event bus
        for component in components:
            self.event_bus.register_component(component)

        # 3. Start API server (if needed) in same async context
        if has_api_component(components):
            await self._start_api_server()

        # 4. Start main event loop
        await self._main_loop()
```

### Phase 3: API Integration
```python
# Simplify: woodwork/components/inputs/api_input.py

class api_input(inputs):
    def __init__(self, **config):
        self.event_bus = get_unified_event_bus()
        self._websocket_sessions = {}

    async def handle_websocket_connection(self, websocket: WebSocket):
        # Direct event subscription - no cross-thread queues
        await self.event_bus.subscribe_to_all_events(
            callback=lambda event: websocket.send_json(event.to_dict())
        )

    async def handle_input(self, user_input: str) -> None:
        # Direct event emission
        payload = InputReceivedPayload(input=user_input, ...)
        await self.event_bus.emit("input.received", payload)
```

## Container Architecture

### Local Development
```python
# Single process, async runtime
runtime = AsyncRuntime()
await runtime.start(config)
```

### Production Deployment
```python
# Each component in container
# Component containers communicate via UnifiedEventBus
# API container handles WebSocket connections
# Message bus container (Redis/NATS) for inter-container events

class ContainerizedComponent:
    async def start(self):
        # Connect to external message bus
        self.event_bus = UnifiedEventBus(transport="redis://message-bus:6379")

        # Process events from other containers
        async for event in self.event_bus.listen():
            await self.handle_event(event)
```

## File Deletions

### Remove Deprecated Code
- `woodwork/core/distributed_startup.py` → Replace with `async_runtime.py`
- `woodwork/core/message_bus/declarative_router.py` → Merge into `unified_event_bus.py`
- `woodwork/core/message_bus/factory.py` → Simplify to transport factory only
- `woodwork/events/events.py` → Replace EventManager with UnifiedEventBus

### Simplify Components
- `api_input.py`: Remove cross-thread processors, use direct async event handling
- Component interfaces: Unify around async event handling

## Testing Strategy

### Integration Tests
```python
async def test_real_time_event_delivery():
    """Test that events are delivered immediately without batching"""
    runtime = AsyncRuntime()
    api_component = api_input()

    events_received = []

    async def capture_events(event):
        events_received.append((time.time(), event.event_type))

    # Subscribe to events
    await runtime.event_bus.subscribe_to_all_events(capture_events)

    # Send input
    start_time = time.time()
    await api_component.handle_input("test message")

    # Verify immediate delivery (< 10ms)
    assert len(events_received) > 0
    first_event_time = events_received[0][0]
    assert (first_event_time - start_time) < 0.01

async def test_container_communication():
    """Test that components can communicate across containers"""
    # Simulate containerized deployment
    bus_container = create_message_bus_container()
    input_container = create_component_container("input", bus_container)
    agent_container = create_component_container("agent", bus_container)

    # Send message from input to agent
    await input_container.send_event("input.received", payload)

    # Verify agent receives message
    received_events = await agent_container.get_received_events(timeout=1.0)
    assert len(received_events) == 1
    assert received_events[0].event_type == "input.received"
```

## Benefits

1. **Eliminates Thread Complexity**: Single async runtime
2. **Real-time Delivery**: Direct event routing without queues
3. **Container Ready**: Designed for distributed deployment
4. **Simplified Codebase**: Single communication system
5. **Better Testing**: Unified event flow is easier to test
6. **Performance**: No cross-thread synchronization overhead