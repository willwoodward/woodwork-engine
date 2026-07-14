"""
Message Bus Integration Layer

This module provides the MessageBusIntegration mixin that adds distributed
message bus capabilities to components.
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional, List, Tuple, AsyncGenerator

from .errors import StreamingChunk, ComponentNotFoundError, ResponseTimeoutError, ComponentError
from .builder import MessageBuilder, RequestContext
from .manager import (
    GlobalMessageBusManager,
    get_global_message_bus_manager,
    register_component_with_message_bus,
    initialize_global_message_bus_integration,
    initialize_global_message_bus_integration_sync,
)
from woodwork.runtime.unified_event_bus import get_global_event_bus

log = logging.getLogger(__name__)

# Re-export for backward compatibility
__all__ = [
    "StreamingChunk",
    "ComponentNotFoundError",
    "ResponseTimeoutError",
    "ComponentError",
    "MessageBuilder",
    "RequestContext",
    "MessageBusIntegration",
    "GlobalMessageBusManager",
    "get_global_message_bus_manager",
    "register_component_with_message_bus",
    "initialize_global_message_bus_integration",
    "initialize_global_message_bus_integration_sync",
]


class MessageBusIntegration:
    """
    Mixin that adds clean, distributed message bus capabilities to components.

    Provides intuitive APIs for component-to-component communication:
    - request() for simple request/response patterns
    - message() for fluent message building
    - request_context() for managed lifecycle
    - request_multiple() for concurrent requests
    - request_stream() for streaming responses
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Message bus integration state
        self._message_bus = None
        self._router = None
        self._integration_ready = False

        config_data = kwargs.get("config", {})

        self.output_targets = self._extract_output_targets(config_data)
        self.session_id = self._extract_session_id(config_data)

        log.debug(
            "[MessageBusIntegration] Extracted output_targets: %s (type: %s), session_id: %s",
            self.output_targets,
            type(self.output_targets),
            self.session_id,
        )
        to_value = config_data.get("to") if config_data else None
        log.debug("[MessageBusIntegration] Config 'to' raw value: %s (type: %s)", to_value, type(to_value))

        # Integration statistics
        self.integration_stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "routing_events": 0,
            "integration_errors": 0,
        }

        component_name = getattr(self, "name", "unknown")
        config_keys = list(config_data.keys()) if config_data else []
        log.debug(
            "[MessageBusIntegration] Initialized for component '%s' with targets: %s (from config: %s)",
            component_name,
            self.output_targets,
            config_keys,
        )

    def _extract_output_targets(self, config: Dict[str, Any]) -> List[str]:
        """Extract 'to:' targets from component configuration"""
        if config is None:
            return []
        to_config = config.get("to", [])

        if isinstance(to_config, str):
            targets = [to_config]
        elif isinstance(to_config, list):
            targets = []
            for target in to_config:
                if hasattr(target, "name"):
                    # Handle component object that was resolved by parser
                    targets.append(target.name)
                else:
                    targets.append(str(target))
        elif hasattr(to_config, "name"):
            # Handle single component object that was resolved by parser
            targets = [to_config.name]
        elif to_config is not None:
            # Try to convert to string as fallback
            target_str = str(to_config)
            if target_str and not target_str.startswith("<"):
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
            config.get("session_id")
            or getattr(self, "session_id", None)
            or config.get("deployment", {}).get("session_id")
            or "default-session"
        )

        return str(session_id)

    async def _ensure_message_bus_integration(self) -> bool:
        """Ensure message bus and router are ready"""
        # Safety check: ensure the integration attributes exist
        if not hasattr(self, "_integration_ready"):
            log.warning("[MessageBusIntegration] Missing _integration_ready attribute, initializing")
            self._integration_ready = False
        if not hasattr(self, "_message_bus"):
            log.warning("[MessageBusIntegration] Missing _message_bus attribute, initializing")
            self._message_bus = None
        if not hasattr(self, "_router"):
            log.warning("[MessageBusIntegration] Missing _router attribute, initializing")
            self._router = None

        if self._integration_ready:
            return True

        try:
            # Get global message bus
            if self._message_bus is None:
                log.debug(
                    "[MessageBusIntegration] Getting global message bus for '%s'", getattr(self, "name", "unknown")
                )
                try:
                    from .factory import get_global_message_bus, _global_message_bus

                    log.debug(
                        "[MessageBusIntegration] Global message bus state: %s",
                        type(_global_message_bus).__name__ if _global_message_bus else "None",
                    )

                    # SIMPLE FIX: Just create a new message bus if none exists
                    # This avoids complex cross-thread issues
                    self._message_bus = await get_global_message_bus()

                    log.debug(
                        "[MessageBusIntegration] Connected to message bus for '%s': %s",
                        getattr(self, "name", "unknown"),
                        type(self._message_bus).__name__ if self._message_bus else "None",
                    )

                    # Double-check that we actually got a message bus
                    if self._message_bus is None:
                        log.error(
                            "[MessageBusIntegration] get_global_message_bus() returned None for '%s'",
                            getattr(self, "name", "unknown"),
                        )
                        return False

                except Exception as import_error:
                    log.error(
                        "[MessageBusIntegration] Failed to import or call get_global_message_bus: %s", import_error
                    )
                    log.exception("[MessageBusIntegration] Import exception details:")
                    return False

            # Setup component message handler
            component_name = getattr(self, "name", "unknown")
            if component_name != "unknown":
                self._message_bus.register_component_handler(component_name, self._handle_bus_message)
                log.debug("[MessageBusIntegration] Registered message handler for '%s'", component_name)

            self._integration_ready = True
            return True

        except Exception as e:
            log.error(
                "[MessageBusIntegration] Failed to setup integration for '%s': %s", getattr(self, "name", "unknown"), e
            )
            log.exception("[MessageBusIntegration] Full exception details:")
            if not hasattr(self, "integration_stats"):
                self.integration_stats = {"integration_errors": 0}
            self.integration_stats["integration_errors"] += 1
            return False

    def set_router(self, router: Any) -> None:
        """Set declarative router for automatic routing"""
        try:
            self._router = router
            component_name = getattr(self, "name", "unknown")
            component_type = getattr(self, "type", "unknown")
            log.debug(
                "[MessageBusIntegration] Set router for component '%s' (type: %s)", component_name, component_type
            )

            # Register message handler to receive responses and other messages
            if hasattr(router, "message_bus"):

                async def response_handler(envelope):
                    """Handle incoming response messages."""
                    log.debug(
                        "[MessageBusIntegration] Component '%s' (%s) received message with payload: %s",
                        component_name,
                        component_type,
                        envelope.payload,
                    )
                    payload = envelope.payload
                    data = payload.get("data", {})

                    # Handle component responses
                    if data.get("response_type") == "component_response":
                        request_id = data.get("request_id")
                        result = data.get("result")
                        source_component = data.get("source_component")

                        log.debug(
                            "[MessageBusIntegration] Processing response for component '%s': request_id=%s, source=%s",
                            component_name,
                            request_id,
                            source_component,
                        )

                        if request_id:
                            # Ensure response storage exists
                            if not hasattr(self, "_received_responses"):
                                self._received_responses = {}

                            self._received_responses[request_id] = {
                                "result": result,
                                "source_component": source_component,
                                "received_at": time.time(),
                            }

                            log.debug(
                                "[MessageBusIntegration] Stored response for component '%s' (request_id: %s)",
                                component_name,
                                request_id,
                            )
                    else:
                        log.debug(
                            "[MessageBusIntegration] Component '%s' received non-response message: %s",
                            component_name,
                            data.get("response_type", "no_response_type"),
                        )

                router.message_bus.register_component_handler(component_name, response_handler)
                log.debug("[MessageBusIntegration] Registered response handler for component '%s'", component_name)
            else:
                log.warning(
                    "[MessageBusIntegration] Router has no message_bus attribute, cannot register handler for '%s'",
                    component_name,
                )
        except Exception as e:
            log.error(
                "[MessageBusIntegration] Failed to set router for component '%s': %s", component_name, e, exc_info=True
            )

    async def send_to_component(self, target_component: str, event_type: str, payload: Dict[str, Any]) -> bool:
        """
        Send message directly to another component (bypasses local hooks/pipes)

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
                sender_component=getattr(self, "name", "unknown"),
            )

            # Send via message bus
            success = await self._message_bus.send_to_component(envelope)

            if success:
                self.integration_stats["messages_sent"] += 1
                log.debug(
                    "[MessageBusIntegration] Sent '%s' from %s to %s",
                    event_type,
                    getattr(self, "name", "unknown"),
                    target_component,
                )
            else:
                log.warning(
                    "[MessageBusIntegration] Failed to send '%s' from %s to %s",
                    event_type,
                    getattr(self, "name", "unknown"),
                    target_component,
                )

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
            component_name = getattr(self, "name", "unknown")
            log.debug(
                "[MessageBusIntegration] Post-processing for '%s': hasattr(output_targets)=%s, event=%s",
                component_name,
                hasattr(self, "output_targets"),
                event,
            )

            if hasattr(self, "output_targets"):
                log.debug("[MessageBusIntegration] output_targets value: %s", self.output_targets)
                # Automatic routing to configured targets (replaces Task Master)
                if self.output_targets and self._should_route_event(event):
                    await self._auto_route_output(event, result)
            else:
                log.error(
                    "[MessageBusIntegration] ERROR: Component '%s' missing output_targets attribute!", component_name
                )

            return result

    async def _process_local_event(self, event: str, data: Any) -> Any:
        """Process event through the unified event bus."""
        try:
            event_bus = get_global_event_bus()
            result = await event_bus.emit(event, data)

            log.debug(
                "[MessageBusIntegration] Processed local event '%s' for %s", event, getattr(self, "name", "unknown")
            )

            return result

        except Exception as e:
            log.error("[MessageBusIntegration] Error processing local event '%s': %s", event, e)
            return data  # Return original data on error

    def _should_route_event(self, event: str) -> bool:
        """Determine if event should be automatically routed to targets"""
        # Route events that indicate component output OR input that needs processing
        routable_events = [
            # Input events that need to be routed to processors
            "input_received",
            "input_processed",
            # Output events that indicate component completion
            "response_generated",
            "processing_complete",
            "result_ready",
            "output_generated",
            "task_complete",
            "data_processed",
        ]

        # Check for exact matches or suffix patterns
        return (
            event in routable_events
            or event.endswith("_generated")
            or event.endswith("_complete")
            or event.endswith("_ready")
            or event.endswith("_processed")
            or event.endswith("_received")
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
                if hasattr(target, "input") and hasattr(target, "name"):
                    try:
                        # For input_received events, extract the actual input
                        if event == "input_received" and hasattr(data, "input"):
                            result = await self._maybe_async(target.input, data.input)
                        elif isinstance(data, dict) and "data" in data:
                            result = await self._maybe_async(target.input, data["data"])
                        else:
                            result = await self._maybe_async(target.input, data)

                        log.debug(
                            "[MessageBusIntegration] Auto-routed '%s' from %s to %s",
                            event,
                            getattr(self, "name", "unknown"),
                            target.name,
                        )

                        # If the target component produced output, route it to the message bus
                        # The declarative router will automatically route it to _console_output
                        if result is not None:
                            await self._route_response_to_console(target.name, result)

                        self.integration_stats["routing_events"] += 1
                    except Exception as e:
                        log.error("[MessageBusIntegration] Error routing to component %s: %s", target.name, e)
                        self.integration_stats["integration_errors"] += 1
                else:
                    # Fallback to message bus routing for non-component targets
                    success = await self.send_to_component(target, event, {"data": data})
                    if success:
                        log.debug(
                            "[MessageBusIntegration] Auto-routed '%s' from %s to %s via message bus",
                            event,
                            getattr(self, "name", "unknown"),
                            target,
                        )
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
            manager = get_global_message_bus_manager()

            # Look for the console output component in registered components
            if hasattr(manager, "_console_output_component") and manager._console_output_component:
                # Call the console component's input method directly
                await self._maybe_async(manager._console_output_component.input, result)
                log.debug(
                    "[MessageBusIntegration] Routed response from %s to console: %s", component_name, str(result)[:100]
                )
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

            log.debug(
                "[MessageBusIntegration] Received '%s' from %s at %s",
                event_type,
                sender,
                getattr(self, "name", "unknown"),
            )

            # Route through unified event bus to apply pipes and hooks
            event_bus = get_global_event_bus()
            await event_bus.emit(event_type, payload.get("data", payload))

            log.debug(
                "[MessageBusIntegration] Processed distributed message '%s' for %s",
                event_type,
                getattr(self, "name", "unknown"),
            )

        except Exception as e:
            log.error("[MessageBusIntegration] Error handling bus message: %s", e)
            self.integration_stats["integration_errors"] += 1

    def get_integration_info(self) -> Dict[str, Any]:
        """Get integration status and configuration"""
        return {
            "component_name": getattr(self, "name", "unknown"),
            "integration_ready": self._integration_ready,
            "session_id": self.session_id,
            "output_targets": self.output_targets,
            "has_router": self._router is not None,
            "has_message_bus": self._message_bus is not None,
            "stats": self.integration_stats.copy(),
        }

    def get_integration_stats(self) -> Dict[str, Any]:
        """Get integration statistics"""
        return {
            **self.integration_stats,
            "component_name": getattr(self, "name", "unknown"),
            "integration_duration": time.time() - getattr(self, "_integration_start_time", time.time()),
            "message_bus_connected": self._message_bus is not None,
            "router_configured": self._router is not None,
        }

    # ============================================================================
    # CLEAN MESSAGE API METHODS
    # ============================================================================

    async def request(self, target_component: str, data: dict, timeout: float = 5.0) -> Any:
        """
        Send request and wait for response in one call.

        Args:
            target_component: Name of target component
            data: Request data to send
            timeout: Maximum time to wait for response

        Returns:
            Response from target component

        Raises:
            ComponentNotFoundError: Target component not found
            ResponseTimeoutError: Response not received in time
            ComponentError: Target component threw an exception
        """
        try:
            # Ensure response handling is set up
            await self._ensure_response_handling()

            # Send request
            log.debug(f"[MessageAPI] Sending request to '{target_component}': {data}")
            success, request_id = await self._router.send_to_component_with_response(
                name=target_component, source_component_name=self.name, data=data
            )

            if not success:
                raise ComponentNotFoundError(f"Failed to send request to component '{target_component}'")

            # Wait for response
            try:
                result = await self._wait_for_response_with_processing(request_id, timeout)
                log.debug(f"[MessageAPI] Request to '{target_component}' completed successfully")
                return result

            except TimeoutError as e:
                raise ResponseTimeoutError(f"Request to '{target_component}' timed out after {timeout}s") from e

        except Exception as e:
            if isinstance(e, (ComponentNotFoundError, ResponseTimeoutError)):
                raise
            else:
                raise ComponentError(f"Error communicating with '{target_component}': {e}") from e

    async def request_multiple(self, requests: List[Tuple[str, dict]], timeout: float = 5.0) -> List[Any]:
        """
        Send multiple requests concurrently and wait for all responses.

        Args:
            requests: List of (target_component, data) tuples
            timeout: Maximum time to wait for all responses

        Returns:
            List of responses in the same order as requests

        Raises:
            ComponentNotFoundError: One or more target components not found
            ResponseTimeoutError: One or more responses not received in time
            ComponentError: One or more target components threw exceptions
        """
        if not requests:
            return []

        log.debug(f"[MessageAPI] Sending {len(requests)} concurrent requests")

        # Create tasks for all requests
        tasks = []
        for target, data in requests:
            task = asyncio.create_task(self.request(target, data, timeout))
            tasks.append(task)

        try:
            # Wait for all requests to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Check for exceptions and re-raise appropriately
            final_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    target, _ = requests[i]
                    if isinstance(result, (ComponentNotFoundError, ResponseTimeoutError, ComponentError)):
                        raise result
                    else:
                        raise ComponentError(f"Error in request to '{target}': {result}") from result
                final_results.append(result)

            log.debug(f"[MessageAPI] All {len(requests)} concurrent requests completed successfully")
            return final_results

        except Exception:
            # Cancel any remaining tasks
            for task in tasks:
                if not task.done():
                    task.cancel()
            raise

    def message(self) -> MessageBuilder:
        """
        Create a fluent message builder.

        Returns:
            MessageBuilder instance for chaining

        Example:
            result = await component.message().to("tool_name").with_data({"action": "test"}).send_and_wait()
        """
        return MessageBuilder(self)

    def request_context(self, target: str, timeout: float = 5.0) -> RequestContext:
        """
        Create a request context manager.

        Args:
            target: Target component name
            timeout: Request timeout

        Returns:
            RequestContext for use with async with

        Example:
            async with component.request_context("tool_name", timeout=5.0) as ctx:
                response = await ctx.send({"action": "test", "inputs": {...}})
        """
        return RequestContext(self, target, timeout)

    async def request_stream(
        self, target: str, data: dict, timeout: float = 30.0
    ) -> AsyncGenerator[StreamingChunk, None]:
        """
        Send request and yield streaming chunks as they arrive.

        Args:
            target: Target component name
            data: Request data
            timeout: Total timeout for the streaming operation

        Yields:
            StreamingChunk objects containing response data

        Example:
            async for chunk in component.request_stream("llm_tool", {"prompt": "Generate text..."}):
                print(chunk.data)
                if chunk.is_final:
                    break
        """
        # For now, this converts regular responses to streaming format
        # In a full implementation, this would integrate with the streaming architecture
        try:
            result = await self.request(target, data, timeout)

            # Convert single response to streaming format
            chunk = StreamingChunk(
                data=result, is_final=True, chunk_index=0, metadata={"response_type": "converted_to_stream"}
            )

            yield chunk

        except Exception as e:
            # Yield error as final chunk
            error_chunk = StreamingChunk(
                data=f"Error: {e}", is_final=True, chunk_index=0, metadata={"error": True, "exception": str(e)}
            )
            yield error_chunk

    async def _ensure_response_handling(self):
        """
        Ensure the component is properly set up to receive and process response messages.

        Components that need custom response handling should override this method.
        """
        # Default implementation for components that have _router
        if not hasattr(self, "_received_responses"):
            self._received_responses = {}

        # Check if we already have a response handler registered
        if hasattr(self, "_response_handler_registered") and self._response_handler_registered:
            return

        # Set up basic response handling if we have a router
        if hasattr(self, "_router") and self._router and hasattr(self._router, "message_bus"):

            async def default_response_handler(envelope):
                """Default handler that processes response messages."""
                try:
                    payload = envelope.payload
                    data = payload.get("data", {})

                    if data.get("response_type") == "component_response":
                        request_id = data.get("request_id")
                        result = data.get("result")
                        source_component = data.get("source_component")

                        if request_id:
                            self._received_responses[request_id] = {
                                "result": result,
                                "source_component": source_component,
                                "received_at": time.time(),
                            }
                            log.debug(f"[MessageAPI] {self.name} stored response for request_id: {request_id}")

                except Exception as e:
                    log.error(f"[MessageAPI] Error processing response message: {e}")

            # Register the handler with the message bus
            self._router.message_bus.register_component_handler(self.name, default_response_handler)
            self._response_handler_registered = True
            log.debug(f"[MessageAPI] Registered default response handler for '{self.name}'")

    async def _wait_for_response_with_processing(self, request_id: str, timeout: float) -> str:
        """
        Wait for response with proper timeout handling.

        Components can override this for custom response waiting logic.
        """
        poll_interval = 0.05  # 50ms polling
        waited = 0.0

        while waited < timeout:
            # Check if response has arrived
            if hasattr(self, "_received_responses") and request_id in self._received_responses:
                response_data = self._received_responses.pop(request_id)
                log.debug(f"[MessageAPI] Found response for request_id '{request_id}': {response_data}")
                return response_data["result"]

            if waited % 1.0 < poll_interval:  # Log every second
                stored_responses = list(self._received_responses.keys()) if hasattr(self, "_received_responses") else []
                log.debug(
                    f"[MessageAPI] Still waiting for response '{request_id}' after {waited:.1f}s, stored responses: {stored_responses}"
                )

            await asyncio.sleep(poll_interval)
            waited += poll_interval

        # Cleanup failed request
        if hasattr(self, "_received_responses"):
            self._received_responses.pop(request_id, None)
        raise TimeoutError(f"Tool response timeout after {timeout}s")
