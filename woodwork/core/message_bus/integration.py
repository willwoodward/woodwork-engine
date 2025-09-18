"""
Message Bus Integration Layer

This module provides seamless integration between the new message bus system and
the existing event system, ensuring no API collisions while enabling distributed
component-to-component communication that replaces Task Master orchestration.
"""

import logging
import time
from typing import Any, Dict, Optional, List

from woodwork.events import get_global_event_manager
from .factory import get_global_message_bus
from .declarative_router import DeclarativeRouter

log = logging.getLogger(__name__)


class MessageBusIntegration:
    """
    Mixin that adds distributed message bus capabilities to components
    
    This integrates seamlessly with the existing event system:
    - emit() continues to work for local events with hooks/pipes
    - send_to_component() enables direct distributed messaging
    - Automatic routing based on 'to:' configuration
    - No API collisions or breaking changes
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Message bus integration state
        self._message_bus = None
        self._router = None
        self._integration_ready = False
        
        config_data = kwargs.get('config', {})
        
        self.output_targets = self._extract_output_targets(config_data)
        self.session_id = self._extract_session_id(config_data)

        log.debug("[MessageBusIntegration] Extracted output_targets: %s (type: %s), session_id: %s",
                  self.output_targets, type(self.output_targets), self.session_id)
        to_value = config_data.get('to') if config_data else None
        log.debug("[MessageBusIntegration] Config 'to' raw value: %s (type: %s)",
                  to_value, type(to_value))
        
        # Integration statistics
        self.integration_stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "routing_events": 0,
            "integration_errors": 0
        }
        
        component_name = getattr(self, 'name', 'unknown')
        config_keys = list(config_data.keys()) if config_data else []
        log.debug("[MessageBusIntegration] Initialized for component '%s' with targets: %s (from config: %s)",
                  component_name, self.output_targets, config_keys)
    
    def _extract_output_targets(self, config: Dict[str, Any]) -> List[str]:
        """Extract 'to:' targets from component configuration"""
        if config is None:
            return []
        to_config = config.get('to', [])
        
        if isinstance(to_config, str):
            targets = [to_config]
        elif isinstance(to_config, list):
            targets = []
            for target in to_config:
                if hasattr(target, 'name'):
                    # Handle component object that was resolved by parser
                    targets.append(target.name)
                else:
                    targets.append(str(target))
        elif hasattr(to_config, 'name'):
            # Handle single component object that was resolved by parser
            targets = [to_config.name]
        elif to_config is not None:
            # Try to convert to string as fallback
            target_str = str(to_config)
            if target_str and not target_str.startswith('<'):
                targets = [target_str]
            else:
                targets = []
        else:
            targets = []
        
        return targets
    
    def _extract_session_id(self, config: Dict[str, Any]) -> str:
        """Extract or generate session ID for component communication"""
        if config is None:
            config = {}
        # Try various sources for session ID
        session_id = (
            config.get('session_id') or
            getattr(self, 'session_id', None) or
            config.get('deployment', {}).get('session_id') or
            'default-session'
        )
        
        return str(session_id)
    
    async def _ensure_message_bus_integration(self) -> bool:
        """Ensure message bus and router are ready"""
        # Safety check: ensure the integration attributes exist
        if not hasattr(self, '_integration_ready'):
            log.warning("[MessageBusIntegration] Missing _integration_ready attribute, initializing")
            self._integration_ready = False
        if not hasattr(self, '_message_bus'):
            log.warning("[MessageBusIntegration] Missing _message_bus attribute, initializing")
            self._message_bus = None
        if not hasattr(self, '_router'):
            log.warning("[MessageBusIntegration] Missing _router attribute, initializing")
            self._router = None

        if self._integration_ready:
            return True

        try:
            # Get global message bus
            if self._message_bus is None:
                log.debug("[MessageBusIntegration] Getting global message bus for '%s'",
                          getattr(self, 'name', 'unknown'))
                try:
                    from .factory import get_global_message_bus, _global_message_bus
                    log.debug("[MessageBusIntegration] Global message bus state: %s",
                              type(_global_message_bus).__name__ if _global_message_bus else 'None')

                    # SIMPLE FIX: Just create a new message bus if none exists
                    # This avoids complex cross-thread issues
                    self._message_bus = await get_global_message_bus()

                    log.debug("[MessageBusIntegration] Connected to message bus for '%s': %s",
                              getattr(self, 'name', 'unknown'), type(self._message_bus).__name__ if self._message_bus else 'None')

                    # Double-check that we actually got a message bus
                    if self._message_bus is None:
                        log.error("[MessageBusIntegration] get_global_message_bus() returned None for '%s'",
                                  getattr(self, 'name', 'unknown'))
                        return False

                except Exception as import_error:
                    log.error("[MessageBusIntegration] Failed to import or call get_global_message_bus: %s", import_error)
                    log.exception("[MessageBusIntegration] Import exception details:")
                    return False
            
            # Setup component message handler
            component_name = getattr(self, 'name', 'unknown')
            if component_name != 'unknown':
                self._message_bus.register_component_handler(component_name, self._handle_bus_message)
                log.debug("[MessageBusIntegration] Registered message handler for '%s'", component_name)
            
            self._integration_ready = True
            return True
            
        except Exception as e:
            log.error("[MessageBusIntegration] Failed to setup integration for '%s': %s",
                      getattr(self, 'name', 'unknown'), e)
            log.exception("[MessageBusIntegration] Full exception details:")
            if not hasattr(self, 'integration_stats'):
                self.integration_stats = {"integration_errors": 0}
            self.integration_stats["integration_errors"] += 1
            return False
    
    def set_router(self, router: DeclarativeRouter) -> None:
        """Set declarative router for automatic routing"""
        try:
            self._router = router
            component_name = getattr(self, 'name', 'unknown')
            component_type = getattr(self, 'type', 'unknown')
            log.debug("[MessageBusIntegration] Set router for component '%s' (type: %s)", component_name, component_type)

            # Register message handler to receive responses and other messages
            if hasattr(router, 'message_bus'):
                async def response_handler(envelope):
                    """Handle incoming response messages."""
                    log.debug("[MessageBusIntegration] Component '%s' (%s) received message with payload: %s",
                              component_name, component_type, envelope.payload)
                    payload = envelope.payload
                    data = payload.get("data", {})

                    # Handle component responses
                    if data.get("response_type") == "component_response":
                        request_id = data.get("request_id")
                        result = data.get("result")
                        source_component = data.get("source_component")

                        log.debug("[MessageBusIntegration] Processing response for component '%s': request_id=%s, source=%s",
                                  component_name, request_id, source_component)

                        if request_id:
                            # Ensure response storage exists
                            if not hasattr(self, '_received_responses'):
                                self._received_responses = {}

                            self._received_responses[request_id] = {
                                "result": result,
                                "source_component": source_component,
                                "received_at": __import__('time').time()
                            }

                            log.debug("[MessageBusIntegration] Stored response for component '%s' (request_id: %s)",
                                      component_name, request_id)
                    else:
                        log.debug("[MessageBusIntegration] Component '%s' received non-response message: %s",
                                  component_name, data.get("response_type", "no_response_type"))

                router.message_bus.register_component_handler(component_name, response_handler)
                log.debug("[MessageBusIntegration] Registered response handler for component '%s'", component_name)
            else:
                log.warning("[MessageBusIntegration] Router has no message_bus attribute, cannot register handler for '%s'", component_name)
        except Exception as e:
            log.error("[MessageBusIntegration] Failed to set router for component '%s': %s", component_name, e, exc_info=True)
    
    async def send_to_component(self, target_component: str, event_type: str, payload: Dict[str, Any]) -> bool:
        """
        Send message directly to another component (bypasses local hooks/pipes)
        
        This provides explicit component-to-component communication without
        going through the local event system.
        
        Args:
            target_component: Name of target component
            event_type: Event type to send
            payload: Message payload
            
        Returns:
            True if message sent successfully
        """
        
        if not await self._ensure_message_bus_integration():
            return False
        
        try:
            from .interface import create_component_message
            
            # Create message envelope
            envelope = create_component_message(
                session_id=self.session_id,
                event_type=event_type,
                payload=payload,
                target_component=target_component,
                sender_component=getattr(self, 'name', 'unknown')
            )
            
            # Send via message bus
            success = await self._message_bus.send_to_component(envelope)
            
            if success:
                self.integration_stats["messages_sent"] += 1
                log.debug("[MessageBusIntegration] Sent '%s' from %s to %s", 
                          event_type, getattr(self, 'name', 'unknown'), target_component)
            else:
                log.warning("[MessageBusIntegration] Failed to send '%s' from %s to %s", 
                           event_type, getattr(self, 'name', 'unknown'), target_component)
            
            return success
            
        except Exception as e:
            log.error("[MessageBusIntegration] Error sending message to %s: %s", target_component, e)
            self.integration_stats["integration_errors"] += 1
            return False
    
    async def emit(self, event: str, data: Any = None, target_component: Optional[str] = None) -> Any:
        """
        Enhanced emit that supports both local and distributed routing
        
        This preserves the existing emit() API while adding optional distributed routing:
        - emit(event, data) -> local processing with hooks/pipes (existing behavior)  
        - emit(event, data, target_component="x") -> direct messaging (new feature)
        
        Args:
            event: Event type
            data: Event data
            target_component: Optional target for direct messaging
            
        Returns:
            Processed data from local event system or original data for distributed
        """
        
        if target_component:
            # Direct component messaging (new distributed feature)
            await self.send_to_component(target_component, event, {"data": data})
            return data
        else:
            # Local event processing (existing behavior)
            result = await self._process_local_event(event, data)
            
            # Debug: Check if output_targets exists before using it
            component_name = getattr(self, 'name', 'unknown')
            log.debug("[MessageBusIntegration] Post-processing for '%s': hasattr(output_targets)=%s, event=%s", 
                      component_name, hasattr(self, 'output_targets'), event)
            
            if hasattr(self, 'output_targets'):
                log.debug("[MessageBusIntegration] output_targets value: %s", self.output_targets)
                # Automatic routing to configured targets (replaces Task Master)
                if self.output_targets and self._should_route_event(event):
                    await self._auto_route_output(event, result)
            else:
                log.error("[MessageBusIntegration] ERROR: Component '%s' missing output_targets attribute!", component_name)
            
            return result
    
    async def _process_local_event(self, event: str, data: Any) -> Any:
        """Process event through existing local event system"""
        try:
            # Get existing event manager 
            event_manager = get_global_event_manager()
            
            # Process through existing hooks and pipes
            result = await event_manager.emit(event, data)
            
            log.debug("[MessageBusIntegration] Processed local event '%s' for %s", 
                      event, getattr(self, 'name', 'unknown'))
            
            return result
            
        except Exception as e:
            log.error("[MessageBusIntegration] Error processing local event '%s': %s", event, e)
            return data  # Return original data on error
    
    def _should_route_event(self, event: str) -> bool:
        """Determine if event should be automatically routed to targets"""
        # Route events that indicate component output OR input that needs processing
        routable_events = [
            # Input events that need to be routed to processors
            'input_received',
            'input_processed',
            # Output events that indicate component completion
            'response_generated',
            'processing_complete', 
            'result_ready',
            'output_generated',
            'task_complete',
            'data_processed'
        ]
        
        # Check for exact matches or suffix patterns
        return (
            event in routable_events or
            event.endswith('_generated') or
            event.endswith('_complete') or
            event.endswith('_ready') or
            event.endswith('_processed') or
            event.endswith('_received')
        )
    
    async def _auto_route_output(self, event: str, data: Any) -> None:
        """Automatically route output to configured targets"""
        if not self.output_targets:
            return
        
        if not await self._ensure_message_bus_integration():
            return
        
        try:
            # Route to each configured target (component objects)
            for target in self.output_targets:
                # If target is a component object, call its input method directly
                if hasattr(target, 'input') and hasattr(target, 'name'):
                    try:
                        # For input_received events, extract the actual input
                        if event == "input_received" and hasattr(data, 'input'):
                            result = await self._maybe_async(target.input, data.input)
                        elif isinstance(data, dict) and 'data' in data:
                            result = await self._maybe_async(target.input, data['data'])
                        else:
                            result = await self._maybe_async(target.input, data)

                        log.debug("[MessageBusIntegration] Auto-routed '%s' from %s to %s",
                                  event, getattr(self, 'name', 'unknown'), target.name)

                        # If the target component produced output, route it to the message bus
                        # The declarative router will automatically route it to _console_output
                        if result is not None:
                            await self._route_response_to_console(target.name, result)

                        self.integration_stats["routing_events"] += 1
                    except Exception as e:
                        log.error("[MessageBusIntegration] Error routing to component %s: %s",
                                  target.name, e)
                        self.integration_stats["integration_errors"] += 1
                else:
                    # Fallback to message bus routing for non-component targets
                    success = await self.send_to_component(target, event, {"data": data})
                    if success:
                        log.debug("[MessageBusIntegration] Auto-routed '%s' from %s to %s via message bus",
                                  event, getattr(self, 'name', 'unknown'), target)
                        self.integration_stats["routing_events"] += 1
            
        except Exception as e:
            log.error("[MessageBusIntegration] Error in auto-routing: %s", e)
            self.integration_stats["integration_errors"] += 1

    async def _maybe_async(self, func, *args, **kwargs):
        """Helper to call either sync or async functions properly"""
        import inspect
        if inspect.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)

    async def _route_response_to_console(self, component_name: str, result: str):
        """Route component response to console output by calling its input() method"""
        try:
            # Get the console output component and call its input method directly
            from woodwork.core.message_bus.integration import get_global_message_bus_manager
            manager = get_global_message_bus_manager()

            # Look for the console output component in registered components
            if hasattr(manager, '_console_output_component') and manager._console_output_component:
                # Call the console component's input method directly
                await self._maybe_async(manager._console_output_component.input, result)
                log.debug("[MessageBusIntegration] Routed response from %s to console: %s",
                         component_name, str(result)[:100])
            else:
                # Fallback to direct print
                print(result)

        except Exception as e:
            log.error("[MessageBusIntegration] Error routing response to console: %s", e)
            # Fallback to direct print
            print(result)

    async def _handle_bus_message(self, envelope) -> None:
        """
        Handle incoming messages from message bus
        
        Routes distributed messages through the existing event system so that
        components' configured pipes and hooks are applied automatically.
        """
        
        try:
            event_type = envelope.event_type
            payload = envelope.payload
            sender = envelope.sender_component
            
            self.integration_stats["messages_received"] += 1
            
            log.debug("[MessageBusIntegration] Received '%s' from %s at %s", 
                      event_type, sender, getattr(self, 'name', 'unknown'))
            
            # Route through existing event system to apply pipes and hooks
            event_manager = get_global_event_manager()
            result = await event_manager.emit(event_type, payload.get('data', payload))
            
            log.debug("[MessageBusIntegration] Processed distributed message '%s' for %s", 
                      event_type, getattr(self, 'name', 'unknown'))
            
        except Exception as e:
            log.error("[MessageBusIntegration] Error handling bus message: %s", e)
            self.integration_stats["integration_errors"] += 1
    
    def get_integration_info(self) -> Dict[str, Any]:
        """Get integration status and configuration"""
        return {
            "component_name": getattr(self, 'name', 'unknown'),
            "integration_ready": self._integration_ready,
            "session_id": self.session_id,
            "output_targets": self.output_targets,
            "has_router": self._router is not None,
            "has_message_bus": self._message_bus is not None,
            "stats": self.integration_stats.copy()
        }
    
    def get_integration_stats(self) -> Dict[str, Any]:
        """Get integration statistics"""
        return {
            **self.integration_stats,
            "component_name": getattr(self, 'name', 'unknown'),
            "integration_duration": time.time() - getattr(self, '_integration_start_time', time.time()),
            "message_bus_connected": self._message_bus is not None,
            "router_configured": self._router is not None
        }


class GlobalMessageBusManager:
    """
    Global manager for coordinating message bus integration across all components
    
    This provides centralized coordination while maintaining the distributed
    nature of individual component communication.
    """
    
    def __init__(self):
        self.router = None
        self.message_bus = None
        self.registered_components = {}
        self.integration_active = False
        
        log.debug("[GlobalMessageBusManager] Initialized")
    
    async def initialize(self, component_configs: Dict[str, Dict[str, Any]]) -> None:
        """Initialize global message bus integration"""
        if self.integration_active:
            log.debug("[GlobalMessageBusManager] Already initialized")
            return
        
        try:
            # Get global message bus
            self.message_bus = await get_global_message_bus()
            log.info("[GlobalMessageBusManager] Connected to global message bus")
            
            # Create and configure router
            self.router = DeclarativeRouter(self.message_bus)
            self.router.configure_from_components(component_configs)
            
            log.info("[GlobalMessageBusManager] Configured declarative router with %d components", 
                     len(component_configs))
            
            # Setup built-in console output handler for components without explicit outputs
            await self._setup_console_output_handler()
            
            # Validate routing configuration
            validation = self.router.validate_routing_configuration()
            if not validation["valid"]:
                log.warning("[GlobalMessageBusManager] Routing configuration issues: %s", 
                           validation["issues"])
            
            if validation["warnings"]:
                log.info("[GlobalMessageBusManager] Routing warnings: %s", validation["warnings"])
            
            self.integration_active = True
            
            log.info("[GlobalMessageBusManager] Message bus integration active: %s", 
                     self.router.get_routing_stats())
            
        except Exception as e:
            log.error("[GlobalMessageBusManager] Failed to initialize integration: %s", e)
            raise
    
    async def _setup_console_output_handler(self):
        """Setup built-in console output handler for automatic console routing"""
        try:
            from woodwork.components.outputs.console import console

            # Create console output component
            console_output = console(name="_console_output")

            # Store reference for direct access
            self._console_output_component = console_output

            # Register as message handler
            self.message_bus.register_component_handler("_console_output", self._handle_console_message)

            log.info("[GlobalMessageBusManager] Console output handler registered")

        except Exception as e:
            log.error("[GlobalMessageBusManager] Failed to setup console output handler: %s", e)
    
    async def _handle_console_message(self, envelope):
        """Handle messages routed to console output with streaming support"""
        try:
            payload = envelope.payload
            data = payload.get("data", payload)
            
            log.debug("[GlobalMessageBusManager] Handling console message: %s", str(data)[:100])
            
            # Handle streaming output (like task_master implementation)
            if isinstance(data, str) and data.startswith("stream:"):
                log.debug("[GlobalMessageBusManager] Detected streaming output, handling as stream")
                await self._handle_streaming_console_output(data)
            else:
                # Handle structured response data
                if isinstance(data, dict) and 'response' in data:
                    print(data['response'])
                elif isinstance(data, str):
                    print(data)
                else:
                    print(str(data))
                
                log.debug("[GlobalMessageBusManager] Displayed regular output to console")
            
        except Exception as e:
            log.error("[GlobalMessageBusManager] Error in console message handler: %s", e)
    
    async def _handle_streaming_console_output(self, stream_data: str):
        """Handle streaming output to console (adapted from task_master)"""
        try:
            # Import stream manager at runtime to avoid circular imports
            from woodwork.core.stream_manager import get_global_stream_manager
            
            # Get global stream manager
            stream_manager = get_global_stream_manager()
            if stream_manager is None:
                log.error("[GlobalMessageBusManager] No stream manager available for console output")
                print(f"\nNo stream manager available. Output: {stream_data}")
                return
            
            # Extract stream ID
            stream_id = stream_data.replace("stream:", "")
            log.debug("[GlobalMessageBusManager] Extracting stream ID: %s", stream_id)
            
            # Give a tiny moment for the stream to be set up
            import asyncio
            await asyncio.sleep(0.001)
            
            # Stream output to console
            log.debug("[GlobalMessageBusManager] Starting to receive stream chunks for %s", stream_id)
            chunk_count = 0
            async for chunk in stream_manager.receive_stream(stream_id):
                chunk_count += 1
                log.debug("[GlobalMessageBusManager] Received chunk %d: '%s'", chunk_count, chunk.data)
                print(chunk.data, end="", flush=True)
            
            print()  # New line at the end
            log.debug("[GlobalMessageBusManager] Finished streaming %d chunks for %s", chunk_count, stream_id)
            
        except Exception as e:
            log.error("[GlobalMessageBusManager] Error handling streaming console output: %s", e)
            # Fallback to simple output
            print(f"Stream output error: {stream_data}")
    
    def register_component(self, component) -> None:
        """Register component with global integration"""
        if not hasattr(component, 'name'):
            log.warning("[GlobalMessageBusManager] Component missing name attribute")
            return
        
        component_name = component.name
        
        # Set router on component if it has integration
        has_set_router = hasattr(component, 'set_router')
        has_router = self.router is not None
        log.debug("[GlobalMessageBusManager] Component '%s': has_set_router=%s, has_router=%s, router_type=%s",
                  component_name, has_set_router, has_router, type(self.router).__name__ if self.router else 'None')

        if has_set_router and has_router:
            component.set_router(self.router)
            log.debug("[GlobalMessageBusManager] Set router on component '%s'", component_name)
        else:
            if not has_set_router:
                log.warning("[GlobalMessageBusManager] Component '%s' missing set_router method", component_name)
            if not has_router:
                log.warning("[GlobalMessageBusManager] No router available to set on component '%s'", component_name)
        
        self.registered_components[component_name] = component
        
        log.debug("[GlobalMessageBusManager] Registered component '%s'", component_name)
    
    async def send_to_component(self, target_component: str, event_type: str, payload: Dict[str, Any]) -> bool:
        """
        Send message directly to another component via the global message bus

        Args:
            target_component: Name of target component
            event_type: Event type to send
            payload: Message payload

        Returns:
            True if message sent successfully
        """
        if not self.integration_active or not self.message_bus:
            log.error("[GlobalMessageBusManager] Cannot send message - integration not active")
            return False

        try:
            from .interface import create_component_message

            # Create message envelope
            envelope = create_component_message(
                session_id="global-manager",
                event_type=event_type,
                payload=payload,
                target_component=target_component,
                sender_component="global-manager"
            )

            # Send via message bus
            success = await self.message_bus.send_to_component(envelope)

            if success:
                log.debug("[GlobalMessageBusManager] Sent '%s' to %s", event_type, target_component)
            else:
                log.warning("[GlobalMessageBusManager] Failed to send '%s' to %s", event_type, target_component)

            return success

        except Exception as e:
            log.error("[GlobalMessageBusManager] Error sending message to %s: %s", target_component, e)
            return False

    def get_manager_stats(self) -> Dict[str, Any]:
        """Get comprehensive manager statistics"""
        return {
            "integration_active": self.integration_active,
            "registered_components": len(self.registered_components),
            "message_bus_healthy": self.message_bus.is_healthy() if self.message_bus else False,
            "router_stats": self.router.get_routing_stats() if self.router else {},
            "component_list": list(self.registered_components.keys())
        }


# Global instance for coordination
_global_manager = GlobalMessageBusManager()


async def initialize_global_message_bus_integration(component_configs: Dict[str, Dict[str, Any]]) -> None:
    """Initialize global message bus integration"""
    await _global_manager.initialize(component_configs)


def initialize_global_message_bus_integration_sync(component_configs: Dict[str, Dict[str, Any]]) -> None:
    """Synchronously initialize global message bus integration"""
    import asyncio
    
    # Try to get existing event loop, create new one if needed
    try:
        loop = asyncio.get_running_loop()
        # We're in an async context, need to run in thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, _global_manager.initialize(component_configs))
            future.result()
    except RuntimeError:
        # No running loop, safe to create new one
        asyncio.run(_global_manager.initialize(component_configs))


def register_component_with_message_bus(component) -> None:
    """Register component with global message bus manager"""
    _global_manager.register_component(component)


def get_global_message_bus_manager() -> GlobalMessageBusManager:
    """Get global message bus manager"""
    return _global_manager