"""
Unified API Input Component - Real-time WebSocket events without threading

This is the refactored API input component that uses the unified event system
for real-time event delivery without cross-thread queues or delays.
"""

import logging
import json
import time
import uuid
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse

from woodwork.components.inputs.inputs import inputs
from woodwork import defaults
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
        self.workflow_entrypoints: Dict[str, str] = config.get("workflow_entrypoints", {})

        # Task master for workflow execution
        self.task_m = config.get("task_m", None)

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
                "user.input.request",
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
            event_type = getattr(payload, "__class__", type(payload)).__name__
            if hasattr(payload, "to_dict"):
                payload_dict = payload.to_dict()
            else:
                payload_dict = payload if isinstance(payload, dict) else {"data": payload}

            # Map payload class name to event type
            mapped_event_type = self._map_payload_class_to_event_type(event_type)

            event_data = {
                "event_type": mapped_event_type,
                "payload": payload_dict,
                "sender_component": getattr(payload, "component_id", "unknown"),
                "session_id": getattr(payload, "session_id", "default"),
                "created_at": time.time(),
            }

            log.debug("[api_input] Real-time event: %s from %s", mapped_event_type, event_data["sender_component"])

            # Special handling for user input requests - create inbox entry
            if mapped_event_type == "user.input.request":
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
                "request_id": payload_dict.get("request_id"),
                "type": "ask_user",
                "title": f"User Input: {payload_dict.get('question', 'Input Required')[:50]}...",
                "description": payload_dict.get("question", "Agent is requesting user input"),
                "context": f"Request from {payload_dict.get('component_id', 'unknown')}",
                "priority": "medium",  # Could be configurable
                "agent_name": payload_dict.get("component_id", "unknown"),
                "session_id": payload_dict.get("session_id", "default"),
                "api_input_id": self.name,
                "workflow_name": None,  # Could extract from payload if available
                "created_at": time.time(),
                "metadata": {
                    "question": payload_dict.get("question"),
                    "timeout_seconds": payload_dict.get("timeout_seconds", 60),
                },
            }

            # Emit as human.input.required for inbox system
            await self.event_bus.emit_from_component(self.name, "human.input.required", inbox_payload)
            log.debug("[api_input] Created inbox entry for user input request: %s", payload_dict.get("request_id"))

        except Exception as e:
            log.error("[api_input] Error creating inbox entry for user request: %s", e)

    async def _forward_event_to_websockets(self, event_data: dict):
        """Forward event to all WebSocket sessions in real-time."""
        if not self._websocket_sessions:
            return

        # Convert to websocket-friendly format
        ws_message = {
            "event": event_data["event_type"],
            "payload": event_data["payload"],
            "sender": event_data["sender_component"],
            "session_id": event_data["session_id"],
            "timestamp": event_data["created_at"],
        }

        # Send to all subscribed sessions
        for session_id, session in list(self._websocket_sessions.items()):
            try:
                # Check if this session cares about this message
                if (
                    "*" in session.subscribed_components  # Subscribed to all
                    or event_data["sender_component"] in session.subscribed_components
                    or event_data["session_id"] == session.session_id
                ):
                    await session.websocket.send_json(ws_message)
                    log.debug("[api_input] Sent real-time event %s to session %s", event_data["event_type"], session_id)

            except Exception as e:
                log.error("[api_input] Error sending to WebSocket session %s: %s", session_id, e)
                # Remove broken session
                if session_id in self._websocket_sessions:
                    del self._websocket_sessions[session_id]

    def _map_payload_class_to_event_type(self, class_name: str) -> str:
        """Map payload class names to event types."""
        mapping = {
            "AgentThoughtPayload": "agent.thought",
            "AgentResponsePayload": "agent.response",
            "ToolObservationPayload": "tool.observation",
            "AgentStepCompletePayload": "agent.step_complete",
            "AgentActionPayload": "agent.action",
            "ToolCallPayload": "tool.call",
            "AgentErrorPayload": "agent.error",
            "InputReceivedPayload": "input.received",
            "UserInputRequestPayload": "user.input.request",
            "UserInputResponsePayload": "user.input.response",
            "GenericPayload": "generic",
        }
        return mapping.get(class_name, class_name.lower())

    async def handle_input(self, user_input: str, request_id: Optional[str] = None) -> None:
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
                    component_type="inputs",
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
                    component_type="inputs",
                )
                await self.event_bus.emit_from_component(self.name, "input.received", payload)
                log.debug("[api_input] Input processed and routed")

        except Exception as e:
            log.error("[api_input] Error processing input: %s", e)

    async def start_server(self) -> None:
        """Start the FastAPI server for API input component with proper KeyboardInterrupt handling."""
        shutdown_requested = False

        try:
            import uvicorn
            import signal

            # Configure uvicorn to run in current async context
            config = uvicorn.Config(
                app=self.app,
                host="0.0.0.0",
                port=self.port,
                log_level="warning",  # Only show warnings and errors, not startup/shutdown info
            )

            server = uvicorn.Server(config)

            # Setup signal handlers for graceful shutdown
            def signal_handler(signum, frame):
                nonlocal shutdown_requested
                log.info("[api_input] Received signal %d, shutting down gracefully...", signum)
                shutdown_requested = True
                server.should_exit = True

            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

            try:
                await server.serve()
            except KeyboardInterrupt:
                shutdown_requested = True
            finally:
                # Re-raise KeyboardInterrupt to propagate shutdown to runtime
                if shutdown_requested:
                    raise KeyboardInterrupt("API server shutdown requested")

        except KeyboardInterrupt:
            # Propagate to runtime
            raise
        except Exception as e:
            log.error("[api_input] Error starting server: %s", e)

    async def setup_websocket_subscription(self, websocket: Any) -> str:
        """Setup WebSocket subscription for real-time events."""
        session_id = str(uuid.uuid4())
        session = WebSocketSession(
            websocket=websocket,
            session_id=session_id,
            subscribed_components=["*"],  # Subscribe to all by default
            created_at=time.time(),
        )

        self._websocket_sessions[session_id] = session
        log.info("[api_input] WebSocket session %s subscribed to all events", session_id)
        return session_id

    def _setup_app_and_routes(self):
        """Setup FastAPI application and routes."""

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            """Application lifespan manager."""
            log.debug("[api_input] Starting FastAPI application")
            yield
            log.debug("[api_input] Shutting down FastAPI application")

        # Create FastAPI app with lifespan manager
        self.app = FastAPI(
            title="Woodwork API Input",
            description="API input component for Woodwork engine",
            version="1.0.0",
            lifespan=lifespan,
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
        self._setup_workflow_routes()
        self._setup_workflow_query_routes()

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
                await websocket.send_json(
                    {
                        "event": "session.connected",
                        "payload": {"session_id": session_id, "subscribed_components": ["*"]},
                    }
                )
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
                    except json.JSONDecodeError:
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
                    return JSONResponse(status_code=400, content={"error": "Input is required"})

                # Process input
                await self.handle_input(user_input, request_id)

                return JSONResponse(content={"status": "success", "message": "Input processed"})

            except Exception as e:
                log.error("[api_input] REST input error: %s", e)
                return JSONResponse(status_code=500, content={"error": str(e)})

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return JSONResponse(
                content={
                    "status": "healthy",
                    "component": self.name,
                    "websocket_sessions": len(self._websocket_sessions),
                    "event_bus_stats": self.event_bus.get_stats(),
                }
            )

        @self.app.get("/")
        async def root():
            """Root endpoint with component information."""
            return JSONResponse(
                content={
                    "component": "api_input",
                    "description": "Woodwork API input component with unified event system",
                    "endpoints": {
                        "websocket": "/input",
                        "rest_input": "/input",
                        "health": "/health",
                        "workflows": "/api/workflows",
                        "agents": "/api/agents",
                    },
                }
            )

    def _setup_workflow_routes(self):
        """Setup workflow entrypoint routes dynamically."""
        if not self.workflow_entrypoints:
            return

        log.info(f"[api_input] Registering {len(self.workflow_entrypoints)} workflow entrypoints")

        for entrypoint_name, route_path in self.workflow_entrypoints.items():
            self._register_workflow_route(entrypoint_name, route_path)

    def _register_workflow_route(self, entrypoint_name: str, route_path: str):
        """Register a single workflow entrypoint route."""

        @self.app.post(route_path)
        async def execute_workflow_entrypoint(request: Request):
            """Execute workflow via entrypoint."""
            try:
                body = await request.json()
                inputs = body.get("inputs", {})
                session_id = body.get("session_id", str(uuid.uuid4()))

                log.info(f"[api_input] Workflow entrypoint '{entrypoint_name}' triggered with inputs: {inputs}")

                # Get workflow executor from task master
                executor = self._get_workflow_executor()

                if not executor:
                    return JSONResponse(
                        status_code=500, content={"status": "error", "error": "Workflow executor not available"}
                    )

                # Execute workflow
                result = await executor.execute_entrypoint(entrypoint_name, inputs, session_id)

                return JSONResponse(content={"status": "success", "entrypoint": entrypoint_name, "result": result})

            except Exception as e:
                log.error(f"[api_input] Workflow entrypoint execution failed: {e}")
                return JSONResponse(status_code=500, content={"status": "error", "error": str(e)})

        log.info(f"[api_input] Registered workflow entrypoint: {route_path} → {entrypoint_name}")

    def _get_workflow_executor(self):
        """Get workflow executor from task master."""
        if hasattr(self, "task_m") and self.task_m:
            # Access workflow executor through task master
            return getattr(self.task_m, "_workflow_executor", None)
        return None

    def _setup_workflow_query_routes(self):
        """Setup routes for querying workflows from Neo4j (for frontend workflow browser)."""

        @self.app.get("/api/tools")
        async def get_tools():
            """Get available tools with schemas from unified event bus."""
            try:
                schemas = [schema.to_dict() for schema in self.event_bus.get_all_tool_schemas()]
                log.info(f"[api_input] Returning {len(schemas)} tool schemas")
                return JSONResponse(content={"tools": schemas})
            except Exception as e:
                log.error(f"[api_input] Error getting tool schemas: {e}")
                return JSONResponse(status_code=500, content={"tools": [], "error": str(e)})

        @self.app.get("/api/workflows/{workflow_id}")
        async def get_workflow_detail(workflow_id: str):
            """Get detailed workflow by ID from Neo4j."""
            try:
                from neo4j import GraphDatabase

                driver = GraphDatabase.driver(defaults.NEO4J_URI, auth=(defaults.NEO4J_USER, defaults.NEO4J_PASSWORD))

                with driver.session() as session:
                    # Get workflow with all actions
                    query = """
                    MATCH (w:Workflow {id: $id})
                    OPTIONAL MATCH (w)-[:CONTAINS]->(a:Action)
                    RETURN w, collect(a) as actions
                    """
                    result = session.run(query, {"id": workflow_id})
                    record = result.single()

                    if not record:
                        driver.close()
                        return JSONResponse(status_code=404, content={"error": "Workflow not found"})

                    workflow_node = record["w"]
                    actions = record["actions"]

                    # Sort actions by sequence and build response
                    sorted_actions = sorted([a for a in actions if a is not None], key=lambda x: x.get("sequence", 0))

                    # Build workflow detail response matching frontend expectations
                    workflow_detail = {
                        "id": workflow_node["id"],
                        "name": workflow_node.get("name", "Unnamed Workflow"),
                        "steps": [
                            {
                                "id": action.get("id", f"action-{i}"),
                                "name": action.get("action", ""),
                                "tool": action.get("tool", ""),
                                "inputs": action.get("inputs", "{}")
                                if isinstance(action.get("inputs"), str)
                                else json.dumps(action.get("inputs", {})),
                                "output": action.get("output", ""),
                                "sequence": action.get("sequence", i),
                                "dependencies": [],
                                "description": f"{action.get('tool', '')} - {action.get('action', '')}",
                            }
                            for i, action in enumerate(sorted_actions)
                        ],
                        "metadata": {
                            "status": workflow_node.get("status", "draft"),
                            "created_at": workflow_node.get("created_at").iso_format()
                            if workflow_node.get("created_at")
                            else None,
                            "completed_at": workflow_node.get("completed_at").iso_format()
                            if workflow_node.get("completed_at")
                            else None,
                            "final_step": len(sorted_actions),
                            "prompt": workflow_node.get("name", "Unnamed Workflow"),
                            "total_actions": len(sorted_actions),
                        },
                        "graph": {
                            "nodes": [
                                {
                                    "id": f"step-{i}",
                                    "type": "action",
                                    "label": f"{action.get('tool', '')}: {action.get('action', '')}",
                                }
                                for i, action in enumerate(sorted_actions)
                            ],
                            "edges": [
                                {"id": f"edge-{i}", "source": f"step-{i}", "target": f"step-{i + 1}", "type": "next"}
                                for i in range(len(sorted_actions) - 1)
                            ],
                        },
                    }

                driver.close()
                return JSONResponse(content=workflow_detail)

            except Exception as e:
                log.error(f"[api_input] Error getting workflow detail: {e}")
                return JSONResponse(status_code=500, content={"error": str(e)})

        @self.app.get("/api/workflows")
        async def get_workflows(
            status: Optional[str] = None, category: Optional[str] = None, search: Optional[str] = None, limit: int = 50
        ):
            """Get workflows from Neo4j database with optional filters."""
            try:
                # Use Neo4j driver directly (not the woodwork component which tries to create a new container)
                from neo4j import GraphDatabase

                driver = GraphDatabase.driver(defaults.NEO4J_URI, auth=(defaults.NEO4J_USER, defaults.NEO4J_PASSWORD))

                # Build query with optional filters
                where_clauses = []
                params = {"limit": limit}

                if status:
                    where_clauses.append("w.status = $status")
                    params["status"] = status

                if search:
                    where_clauses.append("toLower(p.text) CONTAINS toLower($search)")
                    params["search"] = search

                where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

                # Query to get workflows with their actions
                query = f"""
                MATCH (w:Workflow)-[:CONTAINS]->(p:Prompt)
                {where_clause}
                OPTIONAL MATCH (w)-[:CONTAINS]->(a:Action)
                WITH w, p, count(a) as action_count,
                     collect(DISTINCT {{tool: a.tool, action: a.action, sequence: a.sequence}}) as action_types
                RETURN w.id as id,
                       w.status as status,
                       w.source as source,
                       w.created_at as created_at,
                       w.completed_at as completed_at,
                       w.final_step as final_step,
                       p.text as name,
                       action_count,
                       action_types
                ORDER BY w.created_at DESC
                LIMIT $limit
                """

                # Execute query using raw driver
                with driver.session() as session:
                    results = session.run(query, params)  # type: ignore[arg-type]
                    workflows = []

                    for record in results:
                        workflow = {
                            "id": record.get("id", "unknown"),
                            "name": record.get("name", "Unnamed Workflow")[:100],
                            "status": record.get("status", "unknown"),
                            "source": record.get("source", "auto"),
                            "description": f"Workflow with {record.get('action_count', 0)} actions",
                            "actions": [],
                        }

                        # Convert action types to actions format with proper sequence
                        action_types = record.get("action_types", [])
                        sorted_actions = sorted(action_types, key=lambda x: x.get("sequence", 0))

                        for action in sorted_actions[:20]:
                            workflow["actions"].append(
                                {
                                    "sequence": action.get("sequence", 0),
                                    "tool": action.get("tool", "unknown"),
                                    "action": action.get("action", "unknown"),
                                    "inputs": {},
                                    "output": "",
                                }
                            )

                        # Convert Neo4j DateTime objects to ISO strings
                        if record.get("created_at"):
                            created_at = record.get("created_at")
                            workflow["created_at"] = (
                                created_at.iso_format() if hasattr(created_at, "iso_format") else str(created_at)
                            )
                        if record.get("completed_at"):
                            completed_at = record.get("completed_at")
                            workflow["completed_at"] = (
                                completed_at.iso_format() if hasattr(completed_at, "iso_format") else str(completed_at)
                            )

                        workflows.append(workflow)

                driver.close()
                log.info(f"[api_input] Retrieved {len(workflows)} workflows from Neo4j")

                return JSONResponse(content={"workflows": workflows, "total": len(workflows), "categories": []})

            except Exception as e:
                log.error(f"[api_input] Error getting workflows: {e}")
                return JSONResponse(
                    status_code=500, content={"workflows": [], "total": 0, "categories": [], "error": str(e)}
                )

        @self.app.get("/api/agents")
        async def get_agents():
            """Get available agents (returns this component's agent info)."""
            # For now, return basic agent info - could be extended to query multiple agents
            return JSONResponse(
                content={
                    "agents": [
                        {"id": "default", "name": "Orchestrator Agent", "status": "online", "capabilities": ["general"]}
                    ],
                    "total": 1,
                }
            )

        @self.app.post("/api/workflows")
        async def create_workflow(request: Request):
            """Create new workflow in Neo4j."""
            try:
                from woodwork.types.workflows import Workflow
                from neo4j import GraphDatabase

                data = await request.json()
                workflow = Workflow.from_dict(data)
                workflow_id = str(uuid.uuid4())

                # Store in Neo4j
                driver = GraphDatabase.driver(defaults.NEO4J_URI, auth=(defaults.NEO4J_USER, defaults.NEO4J_PASSWORD))

                with driver.session() as session:
                    # Create Workflow node
                    create_query = """
                    CREATE (w:Workflow {
                        id: $id,
                        name: $name,
                        status: 'draft',
                        source: 'manual',
                        created_at: datetime()
                    })
                    RETURN w.id as id
                    """
                    session.run(create_query, {"id": workflow_id, "name": workflow.name})

                    # Create Action nodes
                    for idx, action in enumerate(workflow.plan):
                        action_query = """
                        MATCH (w:Workflow {id: $workflow_id})
                        CREATE (a:Action {
                            id: randomUUID(),
                            tool: $tool,
                            action: $action,
                            inputs: $inputs,
                            output: $output,
                            sequence: $sequence
                        })
                        CREATE (w)-[:CONTAINS]->(a)
                        """
                        session.run(
                            action_query,
                            {
                                "workflow_id": workflow_id,
                                "tool": action.tool,
                                "action": action.action,
                                "inputs": json.dumps(action.inputs),
                                "output": action.output,
                                "sequence": idx,
                            },
                        )

                driver.close()
                log.info(f"[api_input] Created workflow {workflow_id}: {workflow.name}")

                return JSONResponse(content={"id": workflow_id, "name": workflow.name, "status": "success"})

            except Exception as e:
                log.error(f"[api_input] Error creating workflow: {e}")
                return JSONResponse(status_code=500, content={"error": str(e)})

        @self.app.put("/api/workflows/{workflow_id}")
        async def update_workflow(workflow_id: str, request: Request):
            """Update existing workflow in Neo4j."""
            try:
                from neo4j import GraphDatabase

                data = await request.json()

                driver = GraphDatabase.driver(defaults.NEO4J_URI, auth=(defaults.NEO4J_USER, defaults.NEO4J_PASSWORD))

                with driver.session() as session:
                    # Update workflow metadata
                    if "name" in data:
                        session.run(
                            "MATCH (w:Workflow {id: $id}) SET w.name = $name", {"id": workflow_id, "name": data["name"]}
                        )

                    # Update actions if provided
                    if "actions" in data:
                        # Delete old actions
                        session.run(
                            "MATCH (w:Workflow {id: $id})-[:CONTAINS]->(a:Action) DETACH DELETE a", {"id": workflow_id}
                        )

                        # Create new actions
                        for idx, action in enumerate(data["actions"]):
                            action_query = """
                            MATCH (w:Workflow {id: $workflow_id})
                            CREATE (a:Action {
                                id: randomUUID(),
                                tool: $tool,
                                action: $action,
                                inputs: $inputs,
                                output: $output,
                                sequence: $sequence
                            })
                            CREATE (w)-[:CONTAINS]->(a)
                            """
                            session.run(
                                action_query,
                                {
                                    "workflow_id": workflow_id,
                                    "tool": action.get("tool", ""),
                                    "action": action.get("action", ""),
                                    "inputs": json.dumps(action.get("inputs", {})),
                                    "output": action.get("output", ""),
                                    "sequence": action.get("sequence", idx),
                                },
                            )

                driver.close()
                log.info(f"[api_input] Updated workflow {workflow_id}")

                return JSONResponse(content={"status": "success"})

            except Exception as e:
                log.error(f"[api_input] Error updating workflow: {e}")
                return JSONResponse(status_code=500, content={"error": str(e)})

        @self.app.delete("/api/workflows/{workflow_id}")
        async def delete_workflow(workflow_id: str):
            """Delete workflow from Neo4j."""
            try:
                from neo4j import GraphDatabase

                driver = GraphDatabase.driver(defaults.NEO4J_URI, auth=(defaults.NEO4J_USER, defaults.NEO4J_PASSWORD))

                with driver.session() as session:
                    session.run("MATCH (w:Workflow {id: $id}) DETACH DELETE w", {"id": workflow_id})

                driver.close()
                log.info(f"[api_input] Deleted workflow {workflow_id}")

                return JSONResponse(content={"status": "deleted"})

            except Exception as e:
                log.error(f"[api_input] Error deleting workflow: {e}")
                return JSONResponse(status_code=500, content={"error": str(e)})

        @self.app.post("/api/workflows/{workflow_id}/entrypoint")
        async def create_entrypoint(workflow_id: str, request: Request):
            """Create entrypoint for workflow."""
            try:
                from neo4j import GraphDatabase

                data = await request.json()
                entrypoint_name = data["name"]

                driver = GraphDatabase.driver(defaults.NEO4J_URI, auth=(defaults.NEO4J_USER, defaults.NEO4J_PASSWORD))

                with driver.session() as session:
                    query = """
                    MATCH (w:Workflow {id: $workflow_id})
                    MERGE (e:Entrypoint {name: $name})
                    ON CREATE SET
                        e.description = $description,
                        e.input_schema = $schema
                    CREATE (e)-[:EXECUTES]->(w)
                    RETURN e
                    """
                    session.run(
                        query,
                        {
                            "workflow_id": workflow_id,
                            "name": entrypoint_name,
                            "description": data.get("description", ""),
                            "schema": json.dumps(data.get("inputSchema", {})),
                        },
                    )

                driver.close()
                log.info(f"[api_input] Created entrypoint {entrypoint_name} for workflow {workflow_id}")

                return JSONResponse(content={"status": "created"})

            except Exception as e:
                log.error(f"[api_input] Error creating entrypoint: {e}")
                return JSONResponse(status_code=500, content={"error": str(e)})

        @self.app.post("/api/workflows/{workflow_id}/execute")
        async def execute_workflow(workflow_id: str, request: Request):
            """Execute workflow with given inputs."""
            try:
                data = await request.json()
                executor = self._get_workflow_executor()

                if not executor:
                    return JSONResponse(status_code=500, content={"error": "Workflow executor not available"})

                result = await executor.execute_workflow(
                    workflow_id=workflow_id,
                    inputs=data.get("inputs", {}),
                    session_id=data.get("sessionId", str(uuid.uuid4())),
                )

                return JSONResponse(content=result)

            except Exception as e:
                log.error(f"[api_input] Error executing workflow: {e}")
                return JSONResponse(status_code=500, content={"error": str(e)})

        @self.app.post("/api/workflows/match")
        async def match_workflow(request: Request):
            """Match a task to an existing workflow using similarity search."""
            try:
                body = await request.json()
                body.get("task_title", "")

                # For now, return no match - this would use Neo4j similarity search
                # TODO: Implement vector similarity search in Neo4j
                return JSONResponse(content={"canUseWorkflow": False, "message": "No matching workflow found"})
            except Exception as e:
                log.error(f"[api_input] Error matching workflow: {e}")
                return JSONResponse(status_code=500, content={"error": str(e)})

        @self.app.get("/api/event-pipeline")
        async def get_event_pipeline():
            """Get all registered hooks and pipes in the event system."""
            try:
                from woodwork.core.unified_event_bus import get_global_event_bus

                event_bus = get_global_event_bus()

                # Get hooks and pipes from the event bus
                hooks_data = {}
                pipes_data = {}

                # Access internal _hooks and _pipes dictionaries
                if hasattr(event_bus, "_hooks"):
                    for event_name, listeners in event_bus._hooks.items():
                        hooks_data[event_name] = [
                            {
                                "function": getattr(listener, "__name__", str(listener)),
                                "module": getattr(listener, "__module__", "unknown"),
                            }
                            for listener in listeners
                        ]

                if hasattr(event_bus, "_pipes"):
                    for event_name, listeners in event_bus._pipes.items():
                        pipes_data[event_name] = [
                            {
                                "function": getattr(listener, "__name__", str(listener)),
                                "module": getattr(listener, "__module__", "unknown"),
                            }
                            for listener in listeners
                        ]

                return JSONResponse(
                    content={
                        "hooks": hooks_data,
                        "pipes": pipes_data,
                        "event_types": list(set(list(hooks_data.keys()) + list(pipes_data.keys()))),
                    }
                )
            except Exception as e:
                log.error(f"[api_input] Error getting event pipeline: {e}")
                import traceback

                log.error(traceback.format_exc())
                return JSONResponse(status_code=500, content={"error": str(e)})

    def get_stats(self) -> Dict[str, Any]:
        """Get component statistics."""
        return {
            "component_name": self.name,
            "websocket_sessions": len(self._websocket_sessions),
            "port": self.port,
            "event_bus_stats": self.event_bus.get_stats(),
        }

    async def close(self):
        """Close API input component and cleanup resources."""
        log.debug("[api_input] Closing API input component")

        # Close all websocket sessions
        for session_id, session in list(self._websocket_sessions.items()):
            try:
                await session.websocket.close()
            except Exception as e:
                log.debug("[api_input] Error closing websocket %s: %s", session_id, e)

        self._websocket_sessions.clear()
        log.debug("[api_input] Closed all websocket sessions")
