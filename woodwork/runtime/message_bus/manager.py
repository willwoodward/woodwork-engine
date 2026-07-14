"""
Global Message Bus Manager

Provides centralized coordination for message bus integration across all components.
"""

import asyncio
import logging
from typing import Any, Dict

from .factory import get_global_message_bus
from woodwork.runtime.unified_event_bus import get_global_event_bus

log = logging.getLogger(__name__)


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

            # Use unified event bus for routing (replaces DeclarativeRouter)
            unified_event_bus = get_global_event_bus()
            log.warning("[GlobalMessageBusManager] Got global event bus: id=%s", id(unified_event_bus))

            # Set message bus reference on unified event bus for virtual component delivery
            log.warning(
                "[GlobalMessageBusManager] About to set message bus: %s (type=%s)",
                self.message_bus,
                type(self.message_bus).__name__,
            )
            unified_event_bus.set_message_bus(self.message_bus)
            log.warning("[GlobalMessageBusManager] Message bus set on unified event bus")

            # Set router early so it's available for component registration
            self.router = unified_event_bus

            # Register components with unified event bus
            for component_name, config in component_configs.items():
                component_obj = config.get("object")
                if component_obj:
                    unified_event_bus.register_component(component_obj)

            # Configure routing from component relationships
            unified_event_bus.configure_routing()

            log.info(
                "[GlobalMessageBusManager] Configured declarative router with %d components", len(component_configs)
            )

            # Setup built-in console output handler for components without explicit outputs
            await self._setup_console_output_handler()

            # Validate routing configuration
            validation = self.router.validate_routing_configuration()
            if not validation["valid"]:
                log.warning("[GlobalMessageBusManager] Routing configuration issues: %s", validation["issues"])

            if validation["warnings"]:
                log.info("[GlobalMessageBusManager] Routing warnings: %s", validation["warnings"])

            self.integration_active = True

            log.info("[GlobalMessageBusManager] Message bus integration active: %s", self.router.get_routing_stats())

        except Exception as e:
            log.error("[GlobalMessageBusManager] Failed to initialize integration: %s", e)
            raise

    async def _setup_console_output_handler(self):
        """Setup built-in console output handler for automatic console routing"""
        try:
            from woodwork.components.outputs.console import Console

            # Create console output component
            console_output = Console(name="_console_output")

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
            log.debug("[GlobalMessageBusManager] Handling console message payload type: %s", type(payload).__name__)

            # Extract response text from various payload formats
            response_text = None

            if isinstance(payload, dict):
                # asdict() payload: {"component_id": ..., "data": {"response": "..."}}
                if "data" in payload and isinstance(payload["data"], dict):
                    response_text = payload["data"].get("response")
                elif "response" in payload:
                    response_text = payload["response"]
            elif hasattr(payload, "data") and isinstance(payload.data, dict):
                response_text = payload.data.get("response")
            elif isinstance(payload, str):
                response_text = payload

            if response_text is None:
                # Fallback: try to get any string representation
                response_text = str(payload)

            log.debug("[GlobalMessageBusManager] Extracted response: %s", str(response_text)[:100])

            # Handle streaming output
            if isinstance(response_text, str) and response_text.startswith("stream:"):
                log.debug("[GlobalMessageBusManager] Detected streaming output, handling as stream")
                await self._handle_streaming_console_output(response_text)
            else:
                print(response_text)
                log.debug("[GlobalMessageBusManager] Displayed regular output to console")

        except Exception as e:
            log.error("[GlobalMessageBusManager] Error in console message handler: %s", e)

    async def _handle_streaming_console_output(self, stream_data: str):
        """Handle streaming output to console (adapted from task_master)"""
        try:
            # Import stream manager at runtime to avoid circular imports
            from woodwork.runtime.stream_manager import get_global_stream_manager

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
        if not hasattr(component, "name"):
            log.warning("[GlobalMessageBusManager] Component missing name attribute")
            return

        component_name = component.name

        # Set router on component if it has integration
        has_set_router = hasattr(component, "set_router")
        has_router = self.router is not None
        log.debug(
            "[GlobalMessageBusManager] Component '%s': has_set_router=%s, has_router=%s, router_type=%s",
            component_name,
            has_set_router,
            has_router,
            type(self.router).__name__ if self.router else "None",
        )

        if has_set_router and has_router:
            component.set_router(self.router)
            log.debug("[GlobalMessageBusManager] Set router on component '%s'", component_name)

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
                sender_component="global-manager",
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
            "component_list": list(self.registered_components.keys()),
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
        asyncio.get_running_loop()
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
