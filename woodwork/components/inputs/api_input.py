import asyncio
import logging
import json
import threading
import time
import uuid
import queue
from typing import Any, Dict, List
from dataclasses import dataclass
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse

from woodwork.components.inputs.inputs import inputs
from woodwork.utils import format_kwargs
from woodwork.core.message_bus import get_global_message_bus
from woodwork.core.message_bus.interface import create_component_message, MessageEnvelope
from woodwork.events import get_global_event_manager

log = logging.getLogger(__name__)


@dataclass
class WebSocketSession:
    """Represents a websocket session with its own context."""

    websocket: WebSocket
    session_id: str
    subscribed_components: List[str]
    created_at: float


class api_input(inputs):
    """API input component with messaging system integration.

    Features:
    - Uses the new messaging system instead of the old event system
    - Efficient websocket communication: only forwards relevant messages
    - Session-based isolation: each websocket gets its own session
    - Direct component messaging instead of broadcasting all events
    - REST API for direct component communication
    """

    def __init__(self, name="api_input", **config):
        format_kwargs(config, component="input", type="api")
        # Ensure required parameters are set for component base class
        config.setdefault("name", name)
        config.setdefault("component", "input")
        config.setdefault("type", "api")
        super().__init__(**config)

        # Configuration
        self.local: bool = config.get("local", True)
        self.port: int = config.get("port", 8000)
        self.routes: Dict[str, str] = config.get("routes", {})

        # WebSocket session management
        self._websocket_sessions: Dict[str, WebSocketSession] = {}

        # Cross-thread event queue for handling events from different threads
        self._cross_thread_event_queue: queue.Queue = queue.Queue()

        # Priority queue for input.received events (processed first)
        self._priority_event_queue: queue.Queue = queue.Queue()

        # Real-time messaging - uvicorn event loop capture
        self._uvicorn_loop = None

        # Setup FastAPI app with modern lifespan
        self._setup_app_and_routes()

        # Message bus integration
        self._message_bus = None
        self._bus_handler_registered = False

        # Event system integration - register hooks to listen for LLM events
        self._event_hooks_registered = False
        self._setup_event_hooks()

        # Start server if running locally
        if self.local:
            try:
                thread = threading.Thread(target=self._run_uvicorn, daemon=True)
                thread.start()
            except Exception as e:
                log.warning(f"uvicorn not available or failed to start server: {e}")

    def _setup_event_hooks(self):
        """Register hooks to listen for events from the LLM and other components."""
        if not self._event_hooks_registered:
            try:
                event_manager = get_global_event_manager()

                # Register hooks for events that should be forwarded to WebSocket
                relevant_events = [
                    "agent.response",
                    "agent.thought",
                    "agent.action",
                    "tool.call",
                    "tool.observation",
                    "agent.step_complete",
                    "agent.error",
                    "input.received",
                    "llm.response",
                    "workflow.started",
                    "workflow.completed"
                ]

                for event_type in relevant_events:
                    event_manager.on_hook(event_type, self._handle_event)
                    log.debug(f"[{self.name}] Registered hook for {event_type}")

                self._event_hooks_registered = True
                log.info(f"[{self.name}] Registered {len(relevant_events)} event hooks")

            except Exception as e:
                log.error(f"[{self.name}] Failed to register event hooks: {e}")

    def _handle_event(self, payload):
        """Handle events from the event system and forward to WebSocket sessions."""
        try:
            # Extract event type from the payload (it has metadata)
            event_type = getattr(payload, '__class__', type(payload)).__name__
            if hasattr(payload, 'to_dict'):
                payload_dict = payload.to_dict()
            else:
                payload_dict = payload if isinstance(payload, dict) else {'data': payload}

            log.info(f"[{self.name}] Received event: {event_type} - {payload_dict}")

            # Check if we're in the WebSocket thread
            current_thread = threading.current_thread()
            log.info(f"[{self.name}] Event received in thread: {current_thread.name} (id: {current_thread.ident})")

            # Create a message envelope-like structure for consistency
            mapped_event_type = self._map_payload_class_to_event_type(event_type)
            event_data = {
                'event_type': mapped_event_type,
                'payload': payload_dict,
                'sender_component': getattr(payload, 'component_id', 'unknown'),
                'session_id': getattr(payload, 'session_id', 'default'),
                'created_at': time.time()
            }

            # Special handling for input.received - use priority queue for immediate processing
            if mapped_event_type == 'input.received':
                log.info(f"[{self.name}] input.received - adding to priority queue for immediate processing")
                self._priority_event_queue.put(event_data)
                return

            # If we're in a different thread, add event to queue with tiny delay to prevent batching
            if current_thread.name != "MainThread" and "uvicorn" not in current_thread.name.lower():
                # Add event to queue with a tiny delay between events
                import random
                delay = random.uniform(0.001, 0.005)  # 1-5ms random delay

                def delayed_queue():
                    import time
                    time.sleep(delay)
                    self._cross_thread_event_queue.put(event_data)

                thread = threading.Thread(target=delayed_queue, daemon=True)
                thread.start()

                log.info(f"[{self.name}] Queued event {event_data['event_type']} with {delay:.3f}s delay")
                return

            # Forward directly to WebSocket sessions
            log.info(f"[{self.name}] Forwarding event directly to WebSocket sessions")
            asyncio.create_task(self._forward_event_to_websockets(event_data))

        except Exception as e:
            log.error(f"[{self.name}] Error handling event: {e}")

    def _send_immediate_websocket_message(self, event_data: dict):
        """Send WebSocket message immediately using call_soon_threadsafe."""
        if not self._websocket_sessions:
            return

        # Convert to websocket-friendly format
        ws_message = {
            "event": event_data['event_type'],
            "payload": event_data['payload'],
            "sender": event_data['sender_component'],
            "session_id": event_data['session_id'],
            "timestamp": event_data['created_at'],
        }

        # Use the uvicorn event loop if available, stored during WebSocket connections
        if hasattr(self, '_uvicorn_loop') and self._uvicorn_loop is not None:
            # Send to all subscribed sessions immediately via the uvicorn loop
            for session_id, session in list(self._websocket_sessions.items()):
                try:
                    # Check if this session cares about this message
                    if (
                        "*" in session.subscribed_components  # Subscribed to all
                        or event_data['sender_component'] in session.subscribed_components
                        or event_data['session_id'] == session.session_id
                    ):
                        # Try immediate WebSocket write using call_soon_threadsafe
                        def immediate_send():
                            """Send WebSocket message immediately using call_soon_threadsafe."""
                            try:
                                # Create task in uvicorn loop and execute immediately
                                task = self._uvicorn_loop.create_task(session.websocket.send_json(ws_message))
                                # Don't await - fire and forget for immediate execution
                            except Exception as e:
                                log.debug(f"[{self.name}] Immediate send failed: {e}")

                        # Schedule immediate execution in uvicorn thread
                        self._uvicorn_loop.call_soon_threadsafe(immediate_send)

                        # Don't wait for completion - fire and forget for speed
                        log.info(f"[{self.name}] Sent immediate {event_data['event_type']} to session {session_id} at {time.time():.6f}")

                except Exception as e:
                    log.debug(f"[{self.name}] Error in immediate send to {session_id}: {e}")
        else:
            # Fallback to queueing if no uvicorn loop available
            self._cross_thread_event_queue.put(event_data)
            log.debug(f"[{self.name}] No uvicorn loop available, queued {event_data['event_type']}")

    def _map_payload_class_to_event_type(self, class_name: str) -> str:
        """Map payload class names to event types."""
        mapping = {
            'AgentThoughtPayload': 'agent.thought',
            'AgentResponsePayload': 'agent.response',
            'ToolObservationPayload': 'tool.observation',
            'AgentStepCompletePayload': 'agent.step_complete',
            'AgentActionPayload': 'agent.action',
            'ToolCallPayload': 'tool.call',
            'AgentErrorPayload': 'agent.error',
            'InputReceivedPayload': 'input.received',
            'GenericPayload': 'generic'  # Fallback for generic events
        }
        return mapping.get(class_name, class_name.lower())

    async def _forward_event_to_websockets(self, event_data: dict):
        """Forward event to relevant websocket sessions."""
        log.info(f"[{self.name}] Attempting to forward event {event_data['event_type']} to {len(self._websocket_sessions)} sessions")

        if not self._websocket_sessions:
            log.info(f"[{self.name}] No WebSocket sessions available to forward to")
            return

        # Convert to websocket-friendly format
        ws_message = {
            "event": event_data['event_type'],
            "payload": event_data['payload'],
            "sender": event_data['sender_component'],
            "session_id": event_data['session_id'],
            "timestamp": event_data['created_at'],
        }

        # Send to sessions that are subscribed to this event
        disconnected_sessions = []
        for session_id, session in self._websocket_sessions.items():
            try:
                # Check if this session cares about this message
                if (
                    "*" in session.subscribed_components  # Subscribed to all
                    or event_data['sender_component'] in session.subscribed_components
                    or event_data['session_id'] == session.session_id
                ):
                    await session.websocket.send_json(ws_message)
                    log.info(f"[{self.name}] Sent {event_data['event_type']} to WebSocket session {session_id} at {time.time():.6f}")
                else:
                    log.debug(f"[{self.name}] Skipping session {session_id} - not subscribed to {event_data['sender_component']}")

            except Exception as e:
                log.debug(f"Failed to send to websocket session {session_id}: {e}")
                disconnected_sessions.append(session_id)

        # Clean up disconnected sessions
        for session_id in disconnected_sessions:
            self._remove_websocket_session(session_id)

    async def _ensure_message_bus_connection(self):
        """Ensure we're connected to the message bus."""
        if self._message_bus is None:
            self._message_bus = await get_global_message_bus()

            # Register our handler for receiving messages
            if not self._bus_handler_registered:
                self._message_bus.register_component_handler(self.name, self._handle_bus_message)
                self._bus_handler_registered = True
                log.debug(f"[{self.name}] Registered with message bus")

    async def _handle_bus_message(self, envelope: MessageEnvelope):
        """Handle messages received from the message bus."""
        try:
            log.debug(f"[{self.name}] Received message: {envelope.event_type} from {envelope.sender_component}")

            # Check if we're in the same thread as the WebSocket (FastAPI/uvicorn thread)
            current_thread = threading.current_thread()

            # If we're in a different thread, queue the event for cross-thread processing
            if current_thread.name != "MainThread" and "uvicorn" not in current_thread.name.lower():
                log.debug(f"[{self.name}] Cross-thread event detected from {current_thread.name}, queuing...")
                self._cross_thread_event_queue.put(envelope)
                return

            # Filter messages to only forward relevant ones to websockets
            if self._should_forward_to_websocket(envelope):
                await self._forward_to_websockets(envelope)

        except Exception as e:
            log.exception(f"[{self.name}] Error handling bus message: {e}")

    async def _cross_thread_event_processor(self):
        """Periodically process events from the cross-thread queue."""
        log.info(f"[{self.name}] Cross-thread event processor started")

        try:
            while True:
                # Process priority queue first (input.received events)
                priority_processed = 0
                try:
                    while not self._priority_event_queue.empty():
                        try:
                            event_data = self._priority_event_queue.get_nowait()
                            log.info(f"[{self.name}] Processing PRIORITY event: {event_data.get('event_type', 'unknown')}")
                            # Priority events are always event data format
                            await self._forward_event_to_websockets(event_data)
                            priority_processed += 1
                        except queue.Empty:
                            break
                        except Exception as e:
                            log.error(f"[{self.name}] Error processing priority event: {e}")
                except Exception as e:
                    log.error(f"[{self.name}] Error in priority event processing: {e}")

                # Then process regular cross-thread events
                processed_count = 0
                try:
                    while not self._cross_thread_event_queue.empty():
                        try:
                            event_data = self._cross_thread_event_queue.get_nowait()
                            log.info(f"[{self.name}] Processing cross-thread event: {event_data.get('event_type', 'unknown')}")

                            # Check if it's a message envelope or event data
                            if isinstance(event_data, dict) and 'event_type' in event_data:
                                # It's event data from the event system
                                await self._forward_event_to_websockets(event_data)
                            else:
                                # It's a message envelope from the message bus
                                if self._should_forward_to_websocket(event_data):
                                    await self._forward_to_websockets(event_data)

                            processed_count += 1

                        except queue.Empty:
                            break
                        except Exception as e:
                            log.error(f"[{self.name}] Error processing cross-thread event: {e}")

                    total_processed = priority_processed + processed_count
                    if total_processed > 0:
                        log.debug(f"[{self.name}] Processed {priority_processed} priority + {processed_count} regular events")

                except Exception as e:
                    log.error(f"[{self.name}] Error in cross-thread event processor: {e}")

                # Wait before checking again (small interval for responsiveness)
                await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            log.debug(f"[{self.name}] Cross-thread event processor cancelled")
            raise
        except Exception as e:
            log.exception(f"[{self.name}] Cross-thread event processor error: {e}")

    def _should_forward_to_websocket(self, envelope: MessageEnvelope) -> bool:
        """Determine if this message should be forwarded to websocket clients."""
        # Forward all relevant events to websockets (since we subscribe to all by default)
        relevant_event_types = [
            "agent.response",
            "agent.thought",
            "agent.action",
            "tool.observation",
            "agent.step_complete",
            "output.generated",
            "input.received",
            "llm.response",
            "workflow.started",
            "workflow.completed",
        ]

        # Forward if it's a relevant event type
        if envelope.event_type in relevant_event_types:
            return True

        # Also forward if it's from our configured output targets
        if self.output_targets:
            for target in self.output_targets:
                target_name = target.name if hasattr(target, 'name') else str(target)
                if envelope.sender_component == target_name:
                    return True

        return False

    async def _forward_to_websockets(self, envelope: MessageEnvelope):
        """Forward message to relevant websocket sessions."""
        if not self._websocket_sessions:
            return

        # Convert message envelope to websocket-friendly format
        ws_message = {
            "event": envelope.event_type,
            "payload": envelope.payload,
            "sender": envelope.sender_component,
            "session_id": envelope.session_id,
            "timestamp": envelope.created_at,
        }

        # Send to sessions that are subscribed to this component
        disconnected_sessions = []
        for session_id, session in self._websocket_sessions.items():
            try:
                # Check if this session cares about this message
                if (
                    "*" in session.subscribed_components  # Subscribed to all
                    or envelope.sender_component in session.subscribed_components
                    or envelope.session_id == session.session_id
                ):
                    await session.websocket.send_json(ws_message)

            except Exception as e:
                log.debug(f"Failed to send to websocket session {session_id}: {e}")
                disconnected_sessions.append(session_id)

        # Clean up disconnected sessions
        for session_id in disconnected_sessions:
            self._remove_websocket_session(session_id)

    def _remove_websocket_session(self, session_id: str):
        """Remove a websocket session."""
        if session_id in self._websocket_sessions:
            del self._websocket_sessions[session_id]
            log.debug(f"Removed websocket session {session_id}")

    async def _send_user_input_to_components(self, user_input: str, session_id: str):
        """Send user input to configured target components via message bus."""
        await self._ensure_message_bus_connection()

        if not self.output_targets:
            log.warning(f"[{self.name}] No output targets configured for user input")
            return

        # Send input to each configured target component
        for target in self.output_targets:
            try:
                # Extract component name from target (could be object or string)
                target_name = target.name if hasattr(target, 'name') else str(target)

                envelope = create_component_message(
                    session_id=session_id,
                    event_type="input.received",
                    payload={
                        "input": user_input,
                        "source": "api_websocket",
                        "timestamp": asyncio.get_event_loop().time(),
                    },
                    target_component=target_name,
                    sender_component=self.name,
                )

                success = await self._message_bus.send_to_component(envelope)
                if success:
                    log.debug(f"[{self.name}] Sent input to {target_name}")
                else:
                    log.warning(f"[{self.name}] Failed to send input to {target_name}")

            except Exception as e:
                log.exception(f"[{self.name}] Error sending input to {target}: {e}")

    def _setup_app_and_routes(self):
        """Setup FastAPI app with modern lifespan and routes."""

        # Define lifespan for message bus initialization and cross-thread processing
        @asynccontextmanager
        async def lifespan(app):
            """Initialize message bus connection and cross-thread processing on startup."""
            await self._ensure_message_bus_connection()

            # Start cross-thread event processing task
            cross_thread_task = asyncio.create_task(self._cross_thread_event_processor())
            log.debug(f"[{self.name}] Started cross-thread event processor")

            try:
                yield
            finally:
                # Clean up
                cross_thread_task.cancel()
                try:
                    await cross_thread_task
                except asyncio.CancelledError:
                    pass
                log.debug(f"[{self.name}] Stopped cross-thread event processor")

        # Create FastAPI app with lifespan
        self.app = FastAPI(lifespan=lifespan)

        # Setup routes
        self._setup_routes()

    def _setup_routes(self):
        """Setup FastAPI routes for websockets and REST endpoints."""

        @self.app.websocket("/input")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()

            # Create session
            session_id = f"ws_{uuid.uuid4().hex[:12]}"

            # Subscribe to all components by default (use "*" as wildcard)
            subscribed_components = ["*"]  # All components

            session = WebSocketSession(
                websocket=websocket,
                session_id=session_id,
                subscribed_components=subscribed_components,
                created_at=asyncio.get_event_loop().time(),
            )

            self._websocket_sessions[session_id] = session

            # Capture the uvicorn event loop for cross-thread messaging
            if not hasattr(self, '_uvicorn_loop') or self._uvicorn_loop is None:
                self._uvicorn_loop = asyncio.get_event_loop()
                log.info(f"[{self.name}] Captured uvicorn event loop for real-time messaging")

            log.info(f"[{self.name}] WebSocket session {session_id} connected")

            try:
                # Send welcome message
                await websocket.send_json(
                    {
                        "event": "session.connected",
                        "payload": {"session_id": session_id, "subscribed_components": session.subscribed_components},
                    }
                )

                # Listen for incoming messages
                while True:
                    data = await websocket.receive_text()
                    await self._handle_websocket_message(session, data)

            except WebSocketDisconnect:
                log.info(f"[{self.name}] WebSocket session {session_id} disconnected")
            except Exception as e:
                log.exception(f"[{self.name}] WebSocket error for session {session_id}: {e}")
            finally:
                self._remove_websocket_session(session_id)

        # Setup REST routes for direct component communication
        for path, target_component in self.routes.items():
            route_path = f"/{path.strip('/')}"

            async def make_handler(request: Request, _target=target_component):
                try:
                    body = await request.json()
                except Exception:
                    try:
                        body_bytes = await request.body()
                        body = body_bytes.decode()
                    except Exception:
                        body = ""

                # Send via message bus and wait for response
                response = await self._send_rest_request_to_component(body, _target)
                return JSONResponse({"result": response})

            self.app.post(route_path)(make_handler)

    async def _handle_websocket_message(self, session: WebSocketSession, data: str):
        """Handle incoming websocket message from client."""
        try:
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                message = {"input": data}

            message_type = message.get("type", "user_input")

            if message_type == "user_input":
                user_input = message.get("input", "")
                if user_input:
                    await self._send_user_input_to_components(user_input, session.session_id)

            elif message_type == "subscribe":
                # Allow clients to subscribe to specific component events
                components = message.get("components", [])
                session.subscribed_components.extend(components)
                session.subscribed_components = list(set(session.subscribed_components))  # Remove duplicates
                log.debug(f"Session {session.session_id} subscribed to {components}")

            elif message_type == "unsubscribe":
                # Allow clients to unsubscribe from component events
                components = message.get("components", [])
                for comp in components:
                    if comp in session.subscribed_components:
                        session.subscribed_components.remove(comp)
                log.debug(f"Session {session.session_id} unsubscribed from {components}")

        except Exception as e:
            log.exception(f"[{self.name}] Error handling websocket message: {e}")
            await session.websocket.send_json(
                {"event": "error", "payload": {"message": f"Error processing message: {str(e)}"}}
            )

    async def _send_rest_request_to_component(self, data: Any, target_component: str) -> Any:
        """Send REST request to component via message bus and wait for response."""
        await self._ensure_message_bus_connection()

        try:
            # Generate unique request ID for response correlation
            request_id = f"rest_{uuid.uuid4().hex[:12]}"

            envelope = create_component_message(
                session_id=request_id,
                event_type="api.request",
                payload={"data": data, "request_id": request_id, "source": "api_rest"},
                target_component=target_component,
                sender_component=self.name,
            )

            success = await self._message_bus.send_to_component(envelope)
            if not success:
                return {"error": f"Failed to send request to {target_component}"}

            # For now, return success. In a full implementation, we'd wait for response
            # This would require implementing response correlation and timeouts
            return {"status": "sent", "target": target_component}

        except Exception as e:
            log.exception(f"[{self.name}] Error sending REST request to {target_component}: {e}")
            return {"error": f"Internal error: {str(e)}"}

    def _run_uvicorn(self):
        """Run the uvicorn server in a background thread."""
        try:
            import uvicorn

            uvicorn.run(self.app, host="0.0.0.0", port=self.port, log_level="info")
        except Exception as e:
            log.exception(f"[{self.name}] Failed to run uvicorn server: {e}")

    def input_function(self):
        """Required by inputs interface - returns empty string for API components."""
        # API input components handle input via websockets/REST, not polling
        return ""

    def close(self):
        """Clean up resources."""
        log.info(f"[{self.name}] Closing API input component")

        # Close all websocket sessions
        for session_id in list(self._websocket_sessions.keys()):
            self._remove_websocket_session(session_id)

        # Unregister from message bus
        if self._message_bus and self._bus_handler_registered:
            self._message_bus.unregister_component_handler(self.name)
            self._bus_handler_registered = False
