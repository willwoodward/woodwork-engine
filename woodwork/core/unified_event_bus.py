"""
Unified Event Bus - Single event system for all component communication

This replaces EventManager + DeclarativeRouter + MessageBus with a single
async event system that eliminates threading issues and provides real-time delivery.
"""

import asyncio
import logging
import time
from typing import Dict, List, Any, Callable, Optional, Set
from collections import defaultdict

from woodwork.types.events import BasePayload, PayloadRegistry

log = logging.getLogger(__name__)


class UnifiedEventBus:
    """
    Single event system for all component communication.

    Combines functionality from:
    - EventManager (hooks, pipes, events)
    - DeclarativeRouter (component-to-component routing)
    - MessageBus (async message passing)

    All operations are async and run in single event loop - no threading.
    """

    def __init__(self):
        # Component registry
        self._components: Dict[str, Any] = {}

        # Routing configuration (component_name -> [target_components])
        self._routing_table: Dict[str, List[str]] = {}

        # Event subscriptions
        self._hooks: Dict[str, List[Callable]] = defaultdict(list)
        self._pipes: Dict[str, List[Callable]] = defaultdict(list)
        self._events: Dict[str, List[Callable]] = defaultdict(list)

        # Statistics
        self._stats = {
            "events_emitted": 0,
            "components_registered": 0,
            "routes_processed": 0,
            "hooks_executed": 0
        }

        log.debug("[UnifiedEventBus] Initialized")

    def register_component(self, component: Any) -> None:
        """Register component for event delivery and routing"""
        component_name = getattr(component, 'name', str(component))
        self._components[component_name] = component
        self._stats["components_registered"] += 1

        # Set router on components that have MessageBusIntegration
        if hasattr(component, 'set_router') and callable(getattr(component, 'set_router')):
            try:
                component.set_router(self)
                log.debug("[UnifiedEventBus] Set router on component '%s'", component_name)
            except Exception as e:
                log.warning("[UnifiedEventBus] Failed to set router on component '%s': %s", component_name, e)

        log.debug("[UnifiedEventBus] Registered component: %s", component_name)

    def configure_routing(self) -> None:
        """Build routing table from component 'to' properties"""
        log.debug("[UnifiedEventBus] Configuring routing from %d components", len(self._components))

        self._routing_table.clear()

        for component_name, component in self._components.items():
            targets = self._extract_routing_targets(component)
            self._routing_table[component_name] = targets

            if targets:
                log.debug("[UnifiedEventBus] Component '%s' routes to: %s", component_name, targets)

        # Infer missing routing patterns
        self._infer_routing_patterns()

        total_routes = sum(len(targets) for targets in self._routing_table.values())
        log.info("[UnifiedEventBus] Routing configured: %d components, %d routes",
                 len(self._components), total_routes)

    def _extract_routing_targets(self, component: Any) -> List[str]:
        """Extract routing targets from component 'to' property"""
        component_name = getattr(component, 'name', 'unknown')

        # Check multiple possible properties where 'to' config might be stored
        to_config = None
        source_property = None

        # Check common properties where routing targets are stored
        for prop in ['to', '_output', 'output_targets']:
            if hasattr(component, prop):
                value = getattr(component, prop)
                if value is not None:
                    to_config = value
                    source_property = prop
                    break

        log.debug("[UnifiedEventBus] Extracting routing for component '%s': to_config=%s (type=%s, from=%s)",
                 component_name, to_config, type(to_config).__name__, source_property)

        if not to_config:
            log.debug("[UnifiedEventBus] No 'to' config for component '%s' (checked: to, _output, output_targets)", component_name)
            return []

        if isinstance(to_config, str):
            targets = [to_config]
            log.debug("[UnifiedEventBus] String target for '%s': %s", component_name, targets)
            return targets
        elif isinstance(to_config, list):
            targets = [str(target) for target in to_config]
            log.debug("[UnifiedEventBus] List targets for '%s': %s", component_name, targets)
            return targets
        elif hasattr(to_config, 'name'):
            targets = [to_config.name]
            log.debug("[UnifiedEventBus] Object target for '%s': %s", component_name, targets)
            return targets
        else:
            target_str = str(to_config)
            if target_str and not target_str.startswith('<'):
                targets = [target_str]
                log.debug("[UnifiedEventBus] String representation target for '%s': %s", component_name, targets)
                return targets

        log.debug("[UnifiedEventBus] No valid targets extracted for '%s'", component_name)
        return []

    def _infer_routing_patterns(self) -> None:
        """Infer routing patterns for components without explicit configuration"""
        component_types = {}

        for name, component in self._components.items():
            # Get component type from class name
            class_name = component.__class__.__name__.lower()
            if 'input' in class_name or 'api' in class_name:
                component_types[name] = 'input'
            elif 'llm' in class_name or 'agent' in class_name or 'openai' in class_name:
                component_types[name] = 'agent'
            elif 'output' in class_name or 'console' in class_name:
                component_types[name] = 'output'
            else:
                component_types[name] = 'unknown'

        # Find patterns
        inputs = [name for name, type_ in component_types.items() if type_ == 'input']
        agents = [name for name, type_ in component_types.items() if type_ == 'agent']
        outputs = [name for name, type_ in component_types.items() if type_ == 'output']

        # Infer input -> agent routing (only if no explicit routing configured)
        for input_comp in inputs:
            current_routing = self._routing_table.get(input_comp, [])
            if not current_routing and agents:
                # Only infer if component has no explicit routing
                self._routing_table[input_comp] = [agents[0]]
                log.debug("[UnifiedEventBus] Inferred routing: %s -> %s", input_comp, agents[0])
            elif current_routing:
                log.debug("[UnifiedEventBus] Explicit routing preserved: %s -> %s", input_comp, current_routing)

        # Infer agent -> output routing
        for agent_comp in agents:
            if not self._routing_table.get(agent_comp):
                if outputs:
                    self._routing_table[agent_comp] = outputs
                else:
                    self._routing_table[agent_comp] = ["_console_output"]
                log.debug("[UnifiedEventBus] Inferred routing: %s -> %s",
                         agent_comp, self._routing_table[agent_comp])

    def register_hook(self, event_type: str, hook: Callable) -> None:
        """Register hook for event type (read-only, concurrent)"""
        self._hooks[event_type].append(hook)
        log.debug("[UnifiedEventBus] Registered hook for '%s'", event_type)

    def register_pipe(self, event_type: str, pipe: Callable) -> None:
        """Register pipe for event type (transform, sequential)"""
        self._pipes[event_type].append(pipe)
        log.debug("[UnifiedEventBus] Registered pipe for '%s'", event_type)

    def register_event(self, event_type: str, listener: Callable) -> None:
        """Register event listener (fire-and-forget)"""
        self._events[event_type].append(listener)
        log.debug("[UnifiedEventBus] Registered event listener for '%s'", event_type)

    async def emit(self, event_type: str, payload: Any) -> Any:
        """
        Emit event with unified processing:
        1. Process hooks (concurrent)
        2. Process pipes (sequential)
        3. Route to target components
        4. Fire event listeners
        """
        start_time = time.time()

        # Create typed payload
        if not isinstance(payload, BasePayload):
            typed_payload = self._create_typed_payload(event_type, payload)
        else:
            typed_payload = payload

        log.debug("[UnifiedEventBus] Emitting '%s' with payload type: %s",
                 event_type, type(typed_payload).__name__)

        # 1. Process hooks concurrently (read-only)
        await self._process_hooks(event_type, typed_payload)

        # 2. Process pipes sequentially (transform)
        transformed_payload = await self._process_pipes(event_type, typed_payload)

        # 3. Fire event listeners (fire-and-forget)
        self._fire_events(event_type, transformed_payload)

        self._stats["events_emitted"] += 1

        emit_time = (time.time() - start_time) * 1000
        log.debug("[UnifiedEventBus] Event '%s' processed in %.2fms", event_type, emit_time)

        return transformed_payload

    async def emit_from_component(self, source_component: str, event_type: str, payload: Any) -> Any:
        """
        Emit event from specific component and route to its targets
        """
        # First emit normally (hooks, pipes, events)
        processed_payload = await self.emit(event_type, payload)

        # Then route to component targets
        await self._route_to_component_targets(source_component, event_type, processed_payload)

        return processed_payload

    async def _process_hooks(self, event_type: str, payload: BasePayload) -> None:
        """Process hooks concurrently (read-only)"""
        hooks = self._hooks.get(event_type, [])

        if not hooks:
            return

        log.debug("[UnifiedEventBus] Processing %d hooks for '%s'", len(hooks), event_type)

        # Execute all hooks concurrently
        tasks = []
        for hook in hooks:
            try:
                if asyncio.iscoroutinefunction(hook):
                    tasks.append(hook(payload))
                else:
                    # Execute sync hooks in thread pool to avoid blocking
                    tasks.append(asyncio.get_event_loop().run_in_executor(None, hook, payload))
            except Exception as e:
                log.error("[UnifiedEventBus] Error creating hook task for '%s': %s", event_type, e)

        if tasks:
            # Wait for all hooks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Log any hook errors
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    log.error("[UnifiedEventBus] Hook %d failed for '%s': %s", i, event_type, result)

        self._stats["hooks_executed"] += len(hooks)

    async def _process_pipes(self, event_type: str, payload: BasePayload) -> BasePayload:
        """Process pipes sequentially (transform)"""
        pipes = self._pipes.get(event_type, [])

        if not pipes:
            return payload

        log.debug("[UnifiedEventBus] Processing %d pipes for '%s'", len(pipes), event_type)

        current_payload = payload

        for i, pipe in enumerate(pipes):
            try:
                if asyncio.iscoroutinefunction(pipe):
                    result = await pipe(current_payload)
                else:
                    result = pipe(current_payload)

                if result is not None:
                    current_payload = result

            except Exception as e:
                log.error("[UnifiedEventBus] Pipe %d failed for '%s': %s", i, event_type, e)

        return current_payload

    def _fire_events(self, event_type: str, payload: BasePayload) -> None:
        """Fire event listeners (fire-and-forget)"""
        listeners = self._events.get(event_type, [])

        if not listeners:
            return

        log.debug("[UnifiedEventBus] Firing %d event listeners for '%s'", len(listeners), event_type)

        for listener in listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    # Create task for async listeners (fire-and-forget)
                    asyncio.create_task(listener(payload))
                else:
                    # Execute sync listeners directly
                    listener(payload)
            except Exception as e:
                log.error("[UnifiedEventBus] Event listener failed for '%s': %s", event_type, e)

    async def _route_to_component_targets(self, source_component: str, event_type: str, payload: BasePayload) -> None:
        """Route event to component targets based on routing table"""
        targets = self._routing_table.get(source_component, [])

        if not targets:
            return

        log.debug("[UnifiedEventBus] Routing '%s' from '%s' to %d targets: %s",
                 event_type, source_component, len(targets), targets)

        # Route to each target component
        for target_name in targets:
            await self._deliver_to_component(target_name, event_type, payload, source_component)
            self._stats["routes_processed"] += 1

    async def _deliver_to_component(self, target_name: str, event_type: str, payload: BasePayload, source_component: str) -> Any:
        """Deliver event directly to target component"""
        target_component = self._components.get(target_name)

        if not target_component:
            if target_name != "_console_output":  # Skip virtual components
                log.warning("[UnifiedEventBus] Target component '%s' not found", target_name)
            return None

        # Only deliver input.received events to component input methods
        # Other events are processed by hooks/pipes but not delivered as input
        if event_type != "input.received":
            log.debug("[UnifiedEventBus] Skipping delivery of '%s' to component '%s' (not an input event)",
                     event_type, target_name)
            return None

        # Check if component has input method
        if not hasattr(target_component, 'input'):
            log.debug("[UnifiedEventBus] Component '%s' has no input method", target_name)
            return None

        try:
            log.debug("[UnifiedEventBus] Delivering '%s' to component '%s'", event_type, target_name)

            # Prepare input data for input.received events
            if hasattr(payload, 'input'):
                input_data = payload.input
            else:
                input_data = payload

            # Call component input method
            if asyncio.iscoroutinefunction(target_component.input):
                result = await target_component.input(input_data)
            else:
                result = target_component.input(input_data)

            log.debug("[UnifiedEventBus] Component '%s' processed input, result: %s",
                     target_name, str(result)[:100] if result else "None")

            # Auto-emit appropriate response event if component doesn't emit internally
            if result is not None:
                await self._auto_emit_response_event(target_name, target_component, result, event_type)

            return result

        except Exception as e:
            log.error("[UnifiedEventBus] Error delivering to component '%s': %s", target_name, e)
            return None

    async def _auto_emit_response_event(self, component_name: str, component: Any, result: Any, input_event_type: str) -> None:
        """Auto-emit appropriate response event based on component type and result."""
        try:
            # Determine component type
            component_class = component.__class__.__name__.lower()

            # Determine appropriate response event type
            if 'llm' in component_class or 'openai' in component_class:
                response_event_type = "agent.response"
            elif 'agent' in component_class:
                response_event_type = "agent.response"
            elif 'tool' in component_class or 'api' in component_class:
                response_event_type = "tool.observation"
            else:
                response_event_type = "component.response"

            # Create response payload
            from woodwork.types.events import GenericPayload

            response_payload = GenericPayload(
                component_id=component_name,
                component_type=component_class,
                data={
                    'response': str(result),
                    'source_component': component_name,
                    'original_event': input_event_type
                }
            )

            log.debug("[UnifiedEventBus] Auto-emitting '%s' from component '%s'",
                     response_event_type, component_name)

            # Emit the response event
            await self.emit_from_component(component_name, response_event_type, response_payload)

        except Exception as e:
            log.error("[UnifiedEventBus] Error auto-emitting response event from '%s': %s", component_name, e)

    def _create_typed_payload(self, event_type: str, data: Any) -> BasePayload:
        """Create typed payload from event data"""
        # Add component context if available
        from woodwork.types.event_source import EventSource

        context = EventSource.get_current()
        if context and isinstance(data, dict):
            component_id, component_type = context
            data = data.copy()
            data.setdefault('component_id', component_id)
            data.setdefault('component_type', component_type)

        # Create typed payload
        return PayloadRegistry.create_payload(event_type, data)

    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics"""
        return {
            **self._stats,
            "components_count": len(self._components),
            "routing_table_size": len(self._routing_table),
            "total_routes": sum(len(targets) for targets in self._routing_table.values()),
            "hook_subscriptions": sum(len(hooks) for hooks in self._hooks.values()),
            "pipe_subscriptions": sum(len(pipes) for pipes in self._pipes.values()),
            "event_subscriptions": sum(len(events) for events in self._events.values())
        }

    def get_routing_info(self, component_name: str) -> Dict[str, Any]:
        """Get routing information for a component"""
        return {
            "component_name": component_name,
            "targets": self._routing_table.get(component_name, []),
            "is_registered": component_name in self._components,
            "target_count": len(self._routing_table.get(component_name, []))
        }

    # Message Bus Integration compatibility methods
    async def send_to_component_with_response(self, name: str, source_component_name: str, data: dict) -> tuple[bool, str]:
        """Send message to component and return (success, request_id) for response tracking"""
        import uuid

        request_id = str(uuid.uuid4())
        log.debug("[UnifiedEventBus] Sending request to '%s' from '%s' with id '%s'", name, source_component_name, request_id)

        if name not in self._components:
            log.warning("[UnifiedEventBus] Component '%s' not found for request", name)
            return False, request_id

        try:
            # Get target component
            target_component = self._components[name]

            # Call component's input method with data
            result = None
            if hasattr(target_component, 'input'):
                # Handle different input method signatures
                if isinstance(data, dict) and "action" in data and "inputs" in data:
                    # Tool format: input(action, inputs)
                    action = data["action"]
                    inputs = data["inputs"]
                    if asyncio.iscoroutinefunction(target_component.input):
                        result = await target_component.input(action, inputs)
                    else:
                        result = target_component.input(action, inputs)
                else:
                    # Standard format: input(data)
                    if asyncio.iscoroutinefunction(target_component.input):
                        result = await target_component.input(data)
                    else:
                        result = target_component.input(data)

            # Send response back to source component
            if source_component_name in self._components:
                source_component = self._components[source_component_name]
                if hasattr(source_component, '_received_responses'):
                    source_component._received_responses[request_id] = {
                        "result": result,
                        "source_component": name,
                        "received_at": time.time()
                    }
                    log.debug("[UnifiedEventBus] Stored response for request_id '%s' in component '%s'",
                             request_id, source_component_name)

            return True, request_id

        except Exception as e:
            log.error("[UnifiedEventBus] Error processing request to '%s': %s", name, e)
            return False, request_id

    @property
    def message_bus(self):
        """Return self for message_bus compatibility - UnifiedEventBus acts as its own message bus"""
        return self

    def register_component_handler(self, component_name: str, handler: Callable):
        """Register message handler for component (compatibility method)"""
        log.debug("[UnifiedEventBus] Registered handler for component '%s'", component_name)
        # For now, we don't need separate handlers since we handle everything directly


# Global event bus instance
_global_event_bus: Optional[UnifiedEventBus] = None


def get_global_event_bus() -> UnifiedEventBus:
    """Get or create global unified event bus"""
    global _global_event_bus

    if _global_event_bus is None:
        _global_event_bus = UnifiedEventBus()
        log.info("[UnifiedEventBus] Created global event bus instance")

    return _global_event_bus


def set_global_event_bus(event_bus: UnifiedEventBus) -> None:
    """Set custom global event bus"""
    global _global_event_bus
    _global_event_bus = event_bus
    log.info("[UnifiedEventBus] Set custom global event bus")


async def emit(event_type: str, payload: Any) -> Any:
    """Global emit function"""
    return await get_global_event_bus().emit(event_type, payload)


def register_hook(event_type: str, hook: Callable) -> None:
    """Global hook registration"""
    get_global_event_bus().register_hook(event_type, hook)


def register_pipe(event_type: str, pipe: Callable) -> None:
    """Global pipe registration"""
    get_global_event_bus().register_pipe(event_type, pipe)


def register_component(component: Any) -> None:
    """Global component registration"""
    get_global_event_bus().register_component(component)