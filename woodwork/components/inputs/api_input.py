"""
Unified API Input Component - Real-time WebSocket events without threading

This is the refactored API input component that uses the unified event system
for real-time event delivery without cross-thread queues or delays.
"""

import asyncio
import logging
import json
import time
import uuid
from typing import Any, Dict, List
from dataclasses import dataclass
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse

from woodwork.components.inputs.inputs import inputs
from woodwork.utils import format_kwargs
from woodwork.core.unified_event_bus import get_global_event_bus
from woodwork.types import InputReceivedPayload

log = logging.getLogger(__name__)


@dataclass
class WebSocketSession:
    """Represents a websocket session with its own context."""
    websocket: WebSocket
    session_id: str
    subscribed_components: List[str]
    created_at: float


class api_input(inputs):
    """
    API input component with unified async event system.

    Features:
    - Uses unified event bus for real-time communication
    - Direct async WebSocket event delivery (no cross-thread queues)
    - Session-based isolation: each websocket gets its own session
    - Real-time event streaming without batching delays
    - REST API for direct component communication
    """

    def __init__(self, name="api_input", **config):
        format_kwargs(config, component="input", type="api")
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

        # Unified event bus integration (no cross-thread queues)
        self.event_bus = get_global_event_bus()

        # Setup FastAPI app
        self._setup_app_and_routes()

        # Register with event bus
        self.event_bus.register_component(self)

        # Setup real-time event subscriptions
        self._setup_real_time_subscriptions()

        log.info("[api_input] Initialized with unified event system")

    def _setup_real_time_subscriptions(self):
        """Register for real-time event delivery to WebSockets."""
        try:
            # Register hooks for events that should be forwarded to WebSocket
            relevant_events = [
                "input.received",
                "agent.response",
                "agent.thought",
                "agent.action",
                "tool.call",
                "tool.observation",
                "agent.step_complete",
                "agent.error",
                "user.input.request"
            ]

            # Register async hooks for real-time delivery
            for event_type in relevant_events:
                self.event_bus.register_hook(event_type, self._handle_real_time_event)

            log.info("[api_input] Registered for real-time events: %s", relevant_events)

        except Exception as e:
            log.error("[api_input] Failed to setup real-time subscriptions: %s", e)

    async def _handle_real_time_event(self, payload):
        """Handle events from unified event bus and forward to WebSocket sessions in real-time."""
        try:
            # Extract event type
            event_type = getattr(payload, '__class__', type(payload)).__name__
            if hasattr(payload, 'to_dict'):
                payload_dict = payload.to_dict()
            else:
                payload_dict = payload if isinstance(payload, dict) else {'data': payload}

            # Map payload class name to event type
            mapped_event_type = self._map_payload_class_to_event_type(event_type)

            event_data = {
                'event_type': mapped_event_type,
                'payload': payload_dict,
                'sender_component': getattr(payload, 'component_id', 'unknown'),
                'session_id': getattr(payload, 'session_id', 'default'),
                'created_at': time.time()
            }

            log.debug("[api_input] Real-time event: %s from %s",
                     mapped_event_type, event_data['sender_component'])

            # Special handling for user input requests - create inbox entry
            if mapped_event_type == 'user.input.request':
                await self._create_inbox_entry_for_user_request(payload_dict)

            # Forward directly to WebSocket sessions (no queues, no delays)
            await self._forward_event_to_websockets(event_data)

        except Exception as e:
            log.error("[api_input] Error handling real-time event: %s", e)

    async def _create_inbox_entry_for_user_request(self, payload_dict: dict):
        """Create an inbox entry for user input requests."""
        try:
            # Create a human input request for the inbox
            inbox_payload = {
                'request_id': payload_dict.get('request_id'),
                'type': 'ask_user',
                'title': f"User Input: {payload_dict.get('question', 'Input Required')[:50]}...",
                'description': payload_dict.get('question', 'Agent is requesting user input'),
                'context': f"Request from {payload_dict.get('component_id', 'unknown')}",
                'priority': 'medium',  # Could be configurable
                'agent_name': payload_dict.get('component_id', 'unknown'),
                'session_id': payload_dict.get('session_id', 'default'),
                'api_input_id': self.name,
                'workflow_name': None,  # Could extract from payload if available
                'created_at': time.time(),
                'metadata': {
                    'question': payload_dict.get('question'),
                    'timeout_seconds': payload_dict.get('timeout_seconds', 60)
                }
            }

            # Emit as human.input.required for inbox system
            await self.event_bus.emit_from_component(self.name, "human.input.required", inbox_payload)
            log.debug("[api_input] Created inbox entry for user input request: %s",
                     payload_dict.get('request_id'))

        except Exception as e:
            log.error("[api_input] Error creating inbox entry for user request: %s", e)

    async def _forward_event_to_websockets(self, event_data: dict):
        """Forward event to all WebSocket sessions in real-time."""
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

        # Send to all subscribed sessions
        for session_id, session in list(self._websocket_sessions.items()):
            try:
                # Check if this session cares about this message
                if (
                    "*" in session.subscribed_components  # Subscribed to all
                    or event_data['sender_component'] in session.subscribed_components
                    or event_data['session_id'] == session.session_id
                ):
                    await session.websocket.send_json(ws_message)
                    log.debug("[api_input] Sent real-time event %s to session %s",
                             event_data['event_type'], session_id)

            except Exception as e:
                log.error("[api_input] Error sending to WebSocket session %s: %s", session_id, e)
                # Remove broken session
                if session_id in self._websocket_sessions:
                    del self._websocket_sessions[session_id]

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
            'UserInputRequestPayload': 'user.input.request',
            'UserInputResponsePayload': 'user.input.response',
            'GenericPayload': 'generic'
        }
        return mapping.get(class_name, class_name.lower())

    async def handle_input(self, user_input: str, request_id: str = None) -> None:
        """Handle user input and emit through unified event system."""
        try:
            log.debug("[api_input] Processing user input: %s", user_input[:100])

            if request_id:
                # This is a response to a user input request
                from woodwork.types.events import UserInputResponsePayload
                payload = UserInputResponsePayload(
                    response=user_input,
                    request_id=request_id,
                    session_id="api_session",
                    component_id=self.name,
                    component_type="inputs"
                )
                await self.event_bus.emit_from_component(self.name, "user.input.response", payload)
                log.debug("[api_input] User input response processed for request %s", request_id)
            else:
                # Regular input
                payload = InputReceivedPayload(
                    input=user_input,
                    inputs={},
                    session_id="api_session",
                    component_id=self.name,
                    component_type="inputs"
                )
                await self.event_bus.emit_from_component(self.name, "input.received", payload)
                log.debug("[api_input] Input processed and routed")

        except Exception as e:
            log.error("[api_input] Error processing input: %s", e)

    async def start_server(self) -> None:
        """Start the FastAPI server for API input component with proper KeyboardInterrupt handling."""
        try:
            import uvicorn
            import signal

            # Configure uvicorn to run in current async context
            config = uvicorn.Config(
                app=self.app,
                host="0.0.0.0",
                port=self.port,
                log_level="info"
            )

            server = uvicorn.Server(config)

            # Setup signal handlers for graceful shutdown
            def signal_handler(signum, frame):
                log.info("[api_input] Received signal %d, shutting down gracefully...", signum)
                server.should_exit = True

            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

            log.info("[api_input] Starting FastAPI server on port %d", self.port)
            log.info("[api_input] Press Ctrl+C to stop the server")

            try:
                await server.serve()
            except KeyboardInterrupt:
                log.info("[api_input] KeyboardInterrupt received, shutting down...")
            finally:
                log.info("[api_input] Server stopped")

        except Exception as e:
            log.error("[api_input] Error starting server: %s", e)

    async def setup_websocket_subscription(self, websocket: Any) -> str:
        """Setup WebSocket subscription for real-time events."""
        session_id = str(uuid.uuid4())
        session = WebSocketSession(
            websocket=websocket,
            session_id=session_id,
            subscribed_components=["*"],  # Subscribe to all by default
            created_at=time.time()
        )

        self._websocket_sessions[session_id] = session
        log.info("[api_input] WebSocket session %s subscribed to all events", session_id)
        return session_id

    def _setup_app_and_routes(self):
        """Setup FastAPI application and routes."""
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            """Application lifespan manager."""
            log.info("[api_input] Starting FastAPI application")
            yield
            log.info("[api_input] Shutting down FastAPI application")

        # Create FastAPI app with lifespan manager
        self.app = FastAPI(
            title="Woodwork API Input",
            description="API input component for Woodwork engine",
            version="1.0.0",
            lifespan=lifespan
        )

        # Add CORS middleware for browser compatibility
        from fastapi.middleware.cors import CORSMiddleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Setup routes
        self._setup_websocket_routes()
        self._setup_rest_routes()

    def _setup_websocket_routes(self):
        """Setup WebSocket routes for real-time communication."""
        @self.app.websocket("/input")
        async def websocket_endpoint(websocket: WebSocket):
            session_id = None
            try:
                await websocket.accept()
                log.info("[api_input] WebSocket connection accepted")

                # Setup session
                session_id = await self.setup_websocket_subscription(websocket)

                # Send welcome message (compatibility with old API)
                await websocket.send_json({
                    "event": "session.connected",
                    "payload": {
                        "session_id": session_id,
                        "subscribed_components": ["*"]
                    }
                })
                log.info("[api_input] Welcome message sent to session %s", session_id)

                # Keep connection alive and handle incoming messages
                while True:
                    data = await websocket.receive_text()
                    log.debug("[api_input] Received WebSocket data: %r", data)

                    # Handle empty or invalid messages gracefully
                    if not data or not data.strip():
                        log.debug("[api_input] Received empty message, ignoring")
                        continue

                    try:
                        message = json.loads(data)
                        log.debug("[api_input] Parsed message: %s", message)
                    except json.JSONDecodeError as e:
                        log.debug("[api_input] Invalid JSON, treating as plain text: %r", data)
                        # Treat as plain text input (compatibility with old API)
                        message = {"input": data}

                    # Handle message (compatible with old API format)
                    if isinstance(message, dict):
                        message_type = message.get("type", "user_input")  # Default to user_input like old API

                        if message_type == "user_input":
                            # Old API format: {"type": "user_input", "input": "text"}
                            user_input = message.get("input", "")
                            request_id = message.get("request_id")
                            if user_input:
                                await self.handle_input(user_input, request_id)
                        elif message_type == "input":
                            # New API format: {"type": "input", "data": "text"}
                            user_input = message.get("data", "")
                            request_id = message.get("request_id")
                            if user_input:
                                await self.handle_input(user_input, request_id)
                        elif message_type == "subscribe":
                            # Handle subscription requests (old API compatibility)
                            components = message.get("components", [])
                            if session_id in self._websocket_sessions:
                                session = self._websocket_sessions[session_id]
                                session.subscribed_components.extend(components)
                                session.subscribed_components = list(set(session.subscribed_components))
                                log.debug("[api_input] Session %s subscribed to %s", session_id, components)
                        else:
                            log.debug("[api_input] Unknown message type: %s", message_type)
                    else:
                        # Handle direct string input
                        if isinstance(message, str):
                            await self.handle_input(message)

            except WebSocketDisconnect:
                log.info("[api_input] WebSocket session %s disconnected", session_id)
            except Exception as e:
                log.error("[api_input] WebSocket error for session %s: %s", session_id, e)
            finally:
                # Clean up session
                if session_id and session_id in self._websocket_sessions:
                    del self._websocket_sessions[session_id]
                    log.debug("[api_input] Cleaned up session %s", session_id)

    def _setup_rest_routes(self):
        """Setup REST API routes."""
        @self.app.post("/input")
        async def submit_input(request: Request):
            """Submit input via REST API."""
            try:
                data = await request.json()
                user_input = data.get("input", "")
                request_id = data.get("request_id")

                if not user_input:
                    return JSONResponse(
                        status_code=400,
                        content={"error": "Input is required"}
                    )

                # Process input
                await self.handle_input(user_input, request_id)

                return JSONResponse(content={"status": "success", "message": "Input processed"})

            except Exception as e:
                log.error("[api_input] REST input error: %s", e)
                return JSONResponse(
                    status_code=500,
                    content={"error": str(e)}
                )

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return JSONResponse(content={
                "status": "healthy",
                "component": self.name,
                "websocket_sessions": len(self._websocket_sessions),
                "event_bus_stats": self.event_bus.get_stats()
            })

        @self.app.get("/")
        async def root():
            """Root endpoint with component information."""
            return JSONResponse(content={
                "component": "api_input",
                "description": "Woodwork API input component with unified event system",
                "endpoints": {
                    "websocket": "/input",
                    "rest_input": "/input",
                    "health": "/health"
                }
            })

    def get_stats(self) -> Dict[str, Any]:
        """Get component statistics."""
        return {
            "component_name": self.name,
            "websocket_sessions": len(self._websocket_sessions),
            "port": self.port,
            "event_bus_stats": self.event_bus.get_stats()
        }