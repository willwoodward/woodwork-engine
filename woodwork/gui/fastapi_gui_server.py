"""
FastAPI GUI Server that integrates with Woodwork's unified event system.

This server:
- Connects to multiple API input components via WebSocket
- Provides REST APIs for workflows, agents, triggering
- Handles WebSocket communication with frontend
- Manages cross-session inbox for human input requests
"""

import asyncio
import json
import logging
import websockets
import yaml
from typing import Dict, List, Optional, Any
from pathlib import Path
import uuid
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

logger = logging.getLogger(__name__)


# Pydantic models for API requests
class WorkflowTriggerRequest(BaseModel):
    workflowId: str
    inputs: Dict[str, Any]
    targetAgent: Optional[str] = None
    priority: Optional[str] = "medium"
    sessionId: Optional[str] = None


class HumanInputResponse(BaseModel):
    request_id: str
    action: str  # 'approved', 'rejected', 'edited', 'selected', 'responded'
    data: Optional[str] = None
    user_id: str
    responded_at: str


class ChatInputRequest(BaseModel):
    input: Optional[str] = None  # New field for ask_user responses
    message: Optional[str] = None  # Keep old field for backwards compatibility
    request_id: Optional[str] = None  # Added for ask_user responses
    session_id: Optional[str] = None


class FastAPIGUIServer:
    """FastAPI GUI Server with multi-API input support."""

    def __init__(self):
        self.app = FastAPI(title="Woodwork GUI Server")
        self.api_connections: Dict[str, Dict] = {}  # API input connections
        self.frontend_connections: Dict[str, WebSocket] = {}  # Frontend WebSocket connections
        self.pending_requests: Dict[str, Dict] = {}  # Cross-session inbox
        self.request_routing: Dict[str, Dict] = {}   # Request routing info
        self.user_sessions: Dict[str, Dict] = {}     # User sessions
        self.pending_api_requests: Dict[str, asyncio.Future] = {}  # Pending API input requests

        self._setup_routes()

    def _sanitize_for_json(self, data: Any) -> Any:
        """Sanitize data for JSON serialization by removing non-serializable objects."""
        if isinstance(data, dict):
            return {k: self._sanitize_for_json(v) for k, v in data.items()
                   if not str(type(v)).startswith("<class '_thread")}
        elif isinstance(data, list):
            return [self._sanitize_for_json(item) for item in data]
        elif hasattr(data, '__dict__'):
            try:
                return self._sanitize_for_json(vars(data))
            except TypeError:
                return str(data)
        else:
            # Try to determine if it's JSON serializable
            try:
                import json
                json.dumps(data)
                return data
            except (TypeError, ValueError):
                return str(data)

    def _setup_routes(self):
        """Setup FastAPI routes."""

        @self.app.get("/api/workflows")
        async def get_workflows():
            """Get available workflows from all connected API inputs."""
            workflows = await self._discover_workflows()
            return {
                "workflows": workflows,
                "total": len(workflows),
                "categories": list(set(w.get("category", "general") for w in workflows))
            }

        @self.app.get("/api/workflows/get")
        async def get_stored_workflows():
            """Get stored workflows from Neo4j database."""
            try:
                workflows = await self._get_stored_workflows()
                return workflows
            except Exception as e:
                logger.error(f"Error getting stored workflows: {e}")
                # Fallback to mock data if real data unavailable
                return [
                    {
                        "id": "mock-workflow-1",
                        "name": "Example Data Processing",
                        "steps": [
                            {"name": "Load Data", "tool": "file_reader", "description": "Read CSV files from input directory"},
                            {"name": "Clean Data", "tool": "data_cleaner", "description": "Remove duplicates and handle missing values"}
                        ]
                    }
                ]

        @self.app.get("/api/workflows/{workflow_id}")
        async def get_workflow_detail(workflow_id: str):
            """Get detailed workflow information including steps and dependencies."""
            try:
                workflow = await self._get_workflow_detail(workflow_id)
                if workflow:
                    return workflow
                else:
                    raise HTTPException(status_code=404, detail="Workflow not found")
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error getting workflow detail: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/agents")
        async def get_agents():
            """Get available agents from all connected API inputs."""
            try:
                agents = await self._discover_agents()
                # Sanitize agents data to prevent JSON serialization errors
                sanitized_agents = self._sanitize_for_json(agents)
                sanitized_connections = self._sanitize_for_json(
                    [{"id": k, **{key: val for key, val in v.items() if key != "websocket"}}
                     for k, v in self.api_connections.items()]
                )

                return {
                    "agents": sanitized_agents,
                    "capabilities": list(set().union(*(a.get("capabilities", []) for a in sanitized_agents))),
                    "apiInputs": sanitized_connections
                }
            except Exception as e:
                logger.error(f"Error getting agents: {e}")
                return {
                    "agents": [],
                    "capabilities": [],
                    "apiInputs": [],
                    "error": str(e)
                }

        @self.app.post("/api/workflows/trigger")
        async def trigger_workflow(request: WorkflowTriggerRequest):
            """Trigger a workflow on the appropriate API input."""
            result = await self._route_workflow_execution(request)
            return result

        @self.app.get("/api/inbox/requests")
        async def get_inbox_requests():
            """Get all pending human input requests."""
            return {
                "requests": list(self.pending_requests.values()),
                "total": len(self.pending_requests)
            }

        @self.app.post("/api/inbox/respond")
        async def respond_to_inbox_request(response: HumanInputResponse):
            """Respond to a human input request."""
            await self._handle_human_input_response(response)
            return {"status": "success"}

        @self.app.post("/api/input")
        async def send_chat_input(request: ChatInputRequest):
            """Send user input to agents via API inputs."""
            logger.info(f"📨 Received chat input: {request}")
            session_id = request.session_id or str(uuid.uuid4())

            # Get the message content from either field
            message_content = request.input or request.message
            if not message_content:
                raise HTTPException(status_code=400, detail="Either 'input' or 'message' field is required")

            # Check if this is a response to an ask_user request
            if request.request_id:
                # This is a response to an ask_user request, handle via inbox response
                response = HumanInputResponse(
                    request_id=request.request_id,
                    action='responded',
                    data=message_content,
                    user_id='current_user',  # TODO: Get from auth context
                    responded_at=datetime.now().isoformat()
                )
                await self._handle_human_input_response(response)
                return {"status": "success", "session_id": session_id, "message": "Response sent to agent"}
            else:
                # Regular chat message
                success = await self._route_user_message(message_content, session_id)

                if success:
                    return {"status": "success", "session_id": session_id, "message": "Message sent to agent"}
                else:
                    raise HTTPException(status_code=503, detail="No API inputs available to handle message")

        @self.app.get("/api/input")
        async def get_input_status():
            """Get input status and connected API inputs (for compatibility)."""
            return {
                "status": "connected" if self.api_connections else "disconnected",
                "api_inputs": len(self.api_connections),
                "response": "FastAPI GUI server ready for input"
            }

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for frontend communication."""
            await self._handle_frontend_websocket(websocket)

        # Serve React app
        @self.app.get("/")
        async def serve_react_app():
            """Serve the React app."""
            # Use the same path as Flask GUI - relative to this file's location
            dist_path = Path(__file__).parent / "dist"
            return FileResponse(dist_path / "index.html")

        # Mount static files using correct path
        dist_path = Path(__file__).parent / "dist"
        self.app.mount("/", StaticFiles(directory=str(dist_path), html=True), name="static")

    async def _discover_workflows(self) -> List[Dict]:
        """Discover workflows from all connected API inputs."""
        workflows = []

        for api_id, connection in self.api_connections.items():
            if connection["status"] != "connected":
                continue

            try:
                # Query workflows from API input using request-response pattern
                request_id = str(uuid.uuid4())
                message = {
                    "type": "get_workflows",
                    "request_id": request_id
                }

                # Create a future for this request
                future = asyncio.Future()
                self.pending_api_requests[request_id] = future

                await connection["websocket"].send(json.dumps(message))

                try:
                    # Wait for response
                    data = await asyncio.wait_for(future, timeout=5.0)

                    if "workflows" in data:
                        for workflow in data["workflows"]:
                            workflows.append({
                                **workflow,
                                "api_input_id": api_id,
                                "source": api_id
                            })
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout waiting for workflows from {api_id}")
                finally:
                    # Clean up the pending request
                    self.pending_api_requests.pop(request_id, None)

            except Exception as e:
                logger.warning(f"Failed to get workflows from {api_id}: {e}")

        # Fallback: return some example workflows if none found
        if not workflows:
            workflows = [
                {
                    "id": "example_workflow_1",
                    "name": "Example Data Processing",
                    "description": "Example workflow for data processing",
                    "category": "general",
                    "status": "active",
                    "requiredCapabilities": ["general"],
                    "api_input_id": "local",
                    "source": "local"
                }
            ]

        return workflows

    async def _discover_agents(self) -> List[Dict]:
        """Discover agents from all connected API inputs."""
        agents = []

        for api_id, connection in self.api_connections.items():
            if connection["status"] != "connected":
                continue

            try:
                # Query agents from API input using request-response pattern
                request_id = str(uuid.uuid4())
                message = {
                    "type": "get_agents",
                    "request_id": request_id
                }

                # Create a future for this request
                future = asyncio.Future()
                self.pending_api_requests[request_id] = future

                await connection["websocket"].send(json.dumps(message))

                try:
                    # Wait for response
                    data = await asyncio.wait_for(future, timeout=5.0)

                    if "agents" in data:
                        for agent in data["agents"]:
                            # Sanitize agent data before adding
                            sanitized_agent = self._sanitize_for_json(agent)
                            sanitized_agent.update({
                                "api_input_id": api_id,
                                "source": api_id
                            })
                            agents.append(sanitized_agent)
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout waiting for agents from {api_id}")
                finally:
                    # Clean up the pending request
                    self.pending_api_requests.pop(request_id, None)

            except Exception as e:
                logger.warning(f"Failed to get agents from {api_id}: {e}")

        # Fallback: return a default agent if none found
        if not agents:
            agents = [
                {
                    "id": "default_agent",
                    "name": "Default Agent",
                    "capabilities": ["general"],
                    "status": "online",
                    "api_input_id": "local",
                    "source": "local"
                }
            ]

        return agents

    async def _get_stored_workflows(self) -> List[Dict]:
        """Get stored workflows from Neo4j database."""
        try:
            # Try to connect to Neo4j database where workflows are stored
            from woodwork.components.knowledge_bases.graph_databases.neo4j import neo4j

            neo4j_client = neo4j(
                uri="bolt://localhost:7687",
                user="neo4j",
                password="testpassword",
                name="workflows_gui_query"
            )

            # Query to get all completed workflows with their basic info
            query = """
            MATCH (w:Workflow)-[:CONTAINS]->(p:Prompt)
            WHERE w.status = 'completed'
            OPTIONAL MATCH (w)-[:CONTAINS]->(a:Action)
            WITH w, p, count(a) as action_count,
                 collect(DISTINCT {tool: a.tool, action: a.action}) as action_types
            RETURN w.id as id,
                   w.created_at as created_at,
                   w.completed_at as completed_at,
                   w.final_step as final_step,
                   p.text as name,
                   action_count,
                   action_types
            ORDER BY w.completed_at DESC
            LIMIT 50
            """

            results = neo4j_client.run(query)
            workflows = []

            for record in results:
                # Create workflow entry compatible with frontend
                workflow = {
                    "id": record.get("id", "unknown"),
                    "name": record.get("name", "Unnamed Workflow")[:100],  # Truncate long names
                    "steps": []
                }

                # Convert action types to steps format expected by frontend
                action_types = record.get("action_types", [])
                for i, action in enumerate(action_types[:10]):  # Limit to 10 steps for display
                    workflow["steps"].append({
                        "name": f"{action.get('action', 'unknown')}",
                        "tool": action.get('tool', 'unknown'),
                        "description": f"Step {i+1}: {action.get('action', 'unknown')} using {action.get('tool', 'unknown')}"
                    })

                # Add metadata
                workflow["metadata"] = {
                    "created_at": record.get("created_at"),
                    "completed_at": record.get("completed_at"),
                    "final_step": record.get("final_step"),
                    "action_count": record.get("action_count", 0)
                }

                workflows.append(workflow)

            neo4j_client.close()
            logger.info(f"Retrieved {len(workflows)} stored workflows from Neo4j")
            return workflows

        except Exception as e:
            logger.warning(f"Failed to get stored workflows from Neo4j: {e}")
            # Return empty list if Neo4j is unavailable
            return []

    async def _get_workflow_detail(self, workflow_id: str) -> Optional[Dict]:
        """Get detailed workflow information including full step chain and dependencies."""
        try:
            from woodwork.components.knowledge_bases.graph_databases.neo4j import neo4j

            neo4j_client = neo4j(
                uri="bolt://localhost:7687",
                user="neo4j",
                password="testpassword",
                name="workflow_detail_query"
            )

            # Query to get complete workflow with action chain and dependencies
            query = """
            MATCH (w:Workflow {id: $workflow_id})-[:CONTAINS]->(p:Prompt)
            OPTIONAL MATCH (w)-[:CONTAINS]->(a:Action)
            OPTIONAL MATCH (p)-[:STARTS]->(first:Action)
            OPTIONAL MATCH path = (first)-[:NEXT*0..50]->(action:Action)
            WITH w, p, first,
                 CASE WHEN path IS NOT NULL
                      THEN nodes(path)
                      ELSE [first]
                 END as action_sequence
            UNWIND action_sequence as action
            WITH w, p, action
            OPTIONAL MATCH (action)-[:DEPENDS_ON]->(dep:Action)
            WITH w, p, action, collect(DISTINCT {
                id: dep.id,
                tool: dep.tool,
                action: dep.action,
                output: dep.output
            }) as dependencies
            RETURN w.id as workflow_id,
                   w.status as status,
                   w.created_at as created_at,
                   w.completed_at as completed_at,
                   w.final_step as final_step,
                   p.text as prompt,
                   p.id as prompt_id,
                   action.id as action_id,
                   action.tool as tool,
                   action.action as action_name,
                   action.inputs as inputs,
                   action.output as output,
                   action.sequence as sequence,
                   dependencies
            ORDER BY action.sequence
            """

            results = neo4j_client.run(query, {"workflow_id": workflow_id})

            if not results:
                neo4j_client.close()
                return None

            # Build detailed workflow structure
            workflow_data = None
            actions = []

            for record in results:
                if workflow_data is None:
                    workflow_data = {
                        "id": record.get("workflow_id"),
                        "name": record.get("prompt", "Unnamed Workflow"),
                        "status": record.get("status"),
                        "created_at": record.get("created_at"),
                        "completed_at": record.get("completed_at"),
                        "final_step": record.get("final_step"),
                        "prompt": record.get("prompt"),
                        "prompt_id": record.get("prompt_id")
                    }

                if record.get("action_id"):
                    actions.append({
                        "id": record.get("action_id"),
                        "name": record.get("action_name", "unknown"),
                        "tool": record.get("tool", "unknown"),
                        "inputs": record.get("inputs", "{}"),
                        "output": record.get("output", "unknown"),
                        "sequence": record.get("sequence", 0),
                        "dependencies": record.get("dependencies", []),
                        "description": f"{record.get('action_name', 'unknown')} using {record.get('tool', 'unknown')}"
                    })

            # Convert to frontend format
            if workflow_data:
                workflow_detail = {
                    "id": workflow_data["id"],
                    "name": workflow_data["name"],
                    "steps": actions,
                    "metadata": {
                        "status": workflow_data["status"],
                        "created_at": workflow_data["created_at"],
                        "completed_at": workflow_data["completed_at"],
                        "final_step": workflow_data["final_step"],
                        "prompt": workflow_data["prompt"],
                        "total_actions": len(actions)
                    },
                    "graph": {
                        "nodes": [
                            {"id": workflow_data["prompt_id"], "type": "prompt", "label": workflow_data["name"][:50]}
                        ] + [
                            {"id": action["id"], "type": "action", "label": f"{action['tool']}: {action['name']}"}
                            for action in actions
                        ],
                        "edges": self._build_workflow_edges(workflow_data["prompt_id"], actions)
                    }
                }

                neo4j_client.close()
                return workflow_detail

            neo4j_client.close()
            return None

        except Exception as e:
            logger.error(f"Failed to get workflow detail for {workflow_id}: {e}")
            return None

    def _build_workflow_edges(self, prompt_id: str, actions: List[Dict]) -> List[Dict]:
        """Build edges for workflow graph visualization."""
        edges = []

        if not actions:
            return edges

        # Sort actions by sequence
        sorted_actions = sorted(actions, key=lambda x: x.get("sequence", 0))

        # Add edge from prompt to first action
        if sorted_actions:
            edges.append({
                "id": f"{prompt_id}->{sorted_actions[0]['id']}",
                "source": prompt_id,
                "target": sorted_actions[0]["id"],
                "type": "starts"
            })

        # Add sequential edges
        for i in range(len(sorted_actions) - 1):
            current = sorted_actions[i]
            next_action = sorted_actions[i + 1]
            edges.append({
                "id": f"{current['id']}->{next_action['id']}",
                "source": current["id"],
                "target": next_action["id"],
                "type": "next"
            })

        # Add dependency edges
        for action in actions:
            for dep in action.get("dependencies", []):
                edges.append({
                    "id": f"{action['id']}-depends-{dep['id']}",
                    "source": action["id"],
                    "target": dep["id"],
                    "type": "depends_on"
                })

        return edges

    async def _route_workflow_execution(self, request: WorkflowTriggerRequest) -> Dict:
        """Route workflow execution to appropriate API input."""
        # Find the API input that has this workflow
        target_api_input = None

        for api_id, connection in self.api_connections.items():
            if connection["status"] == "connected":
                target_api_input = api_id
                break

        if not target_api_input:
            raise HTTPException(status_code=503, detail="No API inputs available")

        try:
            # Send workflow execution request
            execution_id = f"exec_{uuid.uuid4().hex[:8]}"
            message = {
                "type": "workflow_execution",
                "request_id": str(uuid.uuid4()),
                "payload": {
                    "executionId": execution_id,
                    "workflowId": request.workflowId,
                    "inputs": request.inputs,
                    "sessionId": request.sessionId or f"gui_session_{uuid.uuid4().hex[:8]}",
                    "priority": request.priority,
                    "targetAgent": request.targetAgent
                }
            }

            connection = self.api_connections[target_api_input]
            await connection["websocket"].send(json.dumps(message))

            # For MVP, return success immediately
            return {
                "executionId": execution_id,
                "status": "running",
                "targetAgent": request.targetAgent or "default_agent"
            }

        except Exception as e:
            logger.error(f"Failed to execute workflow: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def _handle_human_input_response(self, response: HumanInputResponse):
        """Handle human input response and route back to correct agent."""
        request_id = response.request_id

        if request_id not in self.request_routing:
            raise HTTPException(status_code=404, detail="Request not found")

        routing_info = self.request_routing[request_id]
        original_request = self.pending_requests.get(request_id, {})

        try:
            # Handle ask_user requests specially
            if original_request.get('type') == 'ask_user' and response.action == 'responded':
                # Send user input response back to the agent
                message = {
                    "type": "user_input",
                    "input": response.data or "",
                    "request_id": request_id
                }

                api_input_id = routing_info["api_input_id"]
                if api_input_id in self.api_connections and self.api_connections[api_input_id]["status"] == "connected":
                    await self.api_connections[api_input_id]["websocket"].send(json.dumps(message))
                    logger.info(f"Sent user response for ask_user request {request_id}: {response.data}")
            else:
                # Handle other types of requests (approval, etc.)
                message = {
                    "type": "human_input_response",
                    "request_id": str(uuid.uuid4()),
                    "payload": {
                        "request_id": request_id,
                        "session_id": routing_info["session_id"],
                        "response": {
                            "action": response.action,
                            "data": response.data,
                            "user_id": response.user_id,
                            "responded_at": response.responded_at
                        }
                    }
                }

                api_input_id = routing_info["api_input_id"]
                if api_input_id in self.api_connections and self.api_connections[api_input_id]["status"] == "connected":
                    await self.api_connections[api_input_id]["websocket"].send(json.dumps(message))

            # Clean up completed request
            self.pending_requests.pop(request_id, None)
            self.request_routing.pop(request_id, None)

            # Notify all frontend clients
            await self._broadcast_to_frontend({
                "type": "inbox_update",
                "payload": {
                    "completed_request": request_id,
                    "total_pending": len(self.pending_requests)
                }
            })

            logger.info(f"Routed human input response for {request_id}")

        except Exception as e:
            logger.error(f"Failed to route human input response: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def _handle_frontend_websocket(self, websocket: WebSocket):
        """Handle WebSocket connection from frontend."""
        await websocket.accept()
        connection_id = str(uuid.uuid4())
        self.frontend_connections[connection_id] = websocket

        logger.info(f"Frontend WebSocket connected: {connection_id}")

        try:
            # Send initial connection info
            await websocket.send_json({
                "type": "connection_established",
                "payload": {
                    "connected_api_inputs": list(self.api_connections.keys()),
                    "pending_requests": len(self.pending_requests)
                }
            })

            # Handle incoming messages
            while True:
                data = await websocket.receive_text()
                try:
                    message = json.loads(data)
                    await self._handle_frontend_message(websocket, message)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON from frontend: {data[:100]}... Error: {e}")
                except Exception as e:
                    logger.error(f"Error handling frontend message: {e}")
                    logger.error(f"Raw message data: {repr(data)}")
                    logger.error(f"Parsed message: {repr(message) if 'message' in locals() else 'Failed to parse'}")

        except WebSocketDisconnect:
            logger.info(f"Frontend WebSocket disconnected: {connection_id}")
        except Exception as e:
            logger.error(f"Frontend WebSocket error: {e}")
        finally:
            self.frontend_connections.pop(connection_id, None)

    async def _handle_frontend_message(self, websocket: WebSocket, message: Dict):
        """Handle message from frontend WebSocket."""
        # Ensure message is a dict
        if not isinstance(message, dict):
            logger.error(f"Expected dict message, got {type(message)}: {repr(message)}")
            return

        message_type = message.get("type")

        if message_type == "human_input_response":
            # Handle human input response
            payload = message["payload"]
            response = HumanInputResponse(**payload)
            await self._handle_human_input_response(response)

        elif message_type == "agent_message":
            # Route message to specific agent
            await self._route_agent_message(message["payload"])

        elif message_type == "register":
            # Handle frontend registration
            try:
                logger.debug(f"Step 1: Accessing payload...")
                payload = message.get("payload", {})
                logger.debug(f"Step 1 success: payload = {payload}")

                logger.debug(f"Step 2: Getting client_type...")
                client_type = payload.get("client_type", "unknown") if isinstance(payload, dict) else "unknown"
                logger.debug(f"Step 2 success: client_type = {client_type}")

                logger.info(f"Frontend client registered: {client_type}")

                logger.debug(f"Step 3: Checking self attributes...")
                logger.debug(f"api_connections type: {type(self.api_connections)}")
                logger.debug(f"pending_requests type: {type(self.pending_requests)}")

                logger.debug(f"Step 4: Building response...")
                try:
                    connected_inputs = list(self.api_connections.keys()) if isinstance(self.api_connections, dict) else []
                    pending_count = len(self.pending_requests) if hasattr(self.pending_requests, '__len__') else 0
                    logger.debug(f"Step 4 success: inputs={len(connected_inputs)}, pending={pending_count}")
                except Exception as inner_e:
                    logger.error(f"Error in step 4: {inner_e}")
                    connected_inputs = []
                    pending_count = 0

                logger.debug(f"Step 5: Creating response data...")
                response_data = {
                    "type": "connection_established",
                    "payload": {
                        "connected_api_inputs": connected_inputs,
                        "pending_requests": pending_count
                    },
                    "timestamp": datetime.now().isoformat()
                }
                logger.debug(f"Step 5 success: {response_data}")

                logger.debug(f"Step 6: Sending response...")
                json_str = json.dumps(response_data)
                logger.debug(f"Step 6a: JSON string created: {len(json_str)} chars")
                await websocket.send_text(json_str)
                logger.debug(f"Step 6 success: Response sent")
            except Exception as e:
                logger.error(f"Error in register handler: {e}")
                logger.error(f"Message type: {type(message)}, content: {repr(message)}")
                raise

        else:
            logger.warning(f"Unknown frontend message type: {message_type}")

    async def _route_agent_message(self, payload: Dict):
        """Route message from frontend to appropriate agent."""
        session_id = payload.get("sessionId")
        agent_message = payload.get("message")

        # For MVP, route to first available API input
        for api_id, connection in self.api_connections.items():
            if connection["status"] == "connected":
                try:
                    message = {
                        "type": "user_input",
                        "request_id": str(uuid.uuid4()),
                        "session_id": session_id,
                        "payload": agent_message
                    }
                    await connection["websocket"].send(json.dumps(message))
                    break
                except Exception as e:
                    logger.error(f"Failed to route message to {api_id}: {e}")

    async def _route_user_message(self, message: str, session_id: str) -> bool:
        """Route user message to available API input."""
        logger.info(f"🚀 Routing message: '{message}' (connections: {len(self.api_connections)})")
        if not self.api_connections:
            logger.warning("❌ No API connections available for routing")
            return False

        # For MVP, route to first available API input
        for api_id, connection in self.api_connections.items():
            if connection["status"] == "connected":
                try:
                    message_payload = {
                        "type": "user_input",
                        "input": message,
                        "session_id": session_id
                    }
                    await connection["websocket"].send(json.dumps(message_payload))
                    logger.info(f"Routed user message to {api_id} for session {session_id}: {message}")
                    logger.debug(f"Full message payload sent: {json.dumps(message_payload, indent=2)}")
                    return True
                except Exception as e:
                    logger.error(f"Failed to route message to {api_id}: {e}")

        return False

    async def _broadcast_to_frontend(self, message: Dict):
        """Broadcast message to all connected frontend clients."""
        disconnected = []

        for connection_id, websocket in self.frontend_connections.items():
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to frontend {connection_id}: {e}")
                disconnected.append(connection_id)

        # Clean up disconnected clients
        for connection_id in disconnected:
            self.frontend_connections.pop(connection_id, None)

    async def connect_to_api_input(self, host: str, port: int) -> Optional[str]:
        """Connect to an API input component."""
        connection_id = f"{host}:{port}"

        try:
            uri = f"ws://{host}:{port}/input"
            websocket = await websockets.connect(uri)

            self.api_connections[connection_id] = {
                "websocket": websocket,
                "host": host,
                "port": port,
                "status": "connected"
            }

            # Start listening for events from this API input
            asyncio.create_task(self._listen_to_api_input(connection_id))

            logger.info(f"Connected to API input: {connection_id}")
            return connection_id

        except Exception as e:
            logger.error(f"Failed to connect to API input {host}:{port}: {e}")
            return None

    async def _listen_to_api_input(self, connection_id: str):
        """Listen for events from an API input."""
        connection = self.api_connections[connection_id]
        websocket = connection["websocket"]

        try:
            while True:
                message = await websocket.recv()
                data = json.loads(message)
                await self._handle_api_input_event(connection_id, data)

        except Exception as e:
            logger.error(f"Error listening to API input {connection_id}: {e}")
            connection["status"] = "disconnected"

    async def _handle_api_input_event(self, api_input_id: str, event: Dict):
        """Handle event from API input."""
        event_type = event.get("event")
        request_id = event.get("request_id")

        # Check if this is a response to a pending request
        if request_id and request_id in self.pending_api_requests:
            future = self.pending_api_requests.pop(request_id)
            if not future.done():
                future.set_result(event.get("payload", event))
            return

        if event_type == "human.input.required":
            # Handle human input request
            await self._handle_human_input_request(api_input_id, event["payload"])

        elif event_type in [
            "agent.thought", "agent.action", "agent.response", "agent.step_complete", "agent.error",
            "tool.call", "tool.observation", "input.received", "workflow.started", "workflow.completed",
            "user.input.request"
        ]:
            # Forward agent events to frontend with enhanced structure
            await self._broadcast_to_frontend({
                "type": event_type,
                "payload": event.get("payload", {}),
                "timestamp": event.get("timestamp") or datetime.now().isoformat(),
                "api_input_id": api_input_id
            })

        else:
            logger.debug(f"Received event from {api_input_id}: {event_type}")

    async def _handle_human_input_request(self, api_input_id: str, payload: Dict):
        """Handle human input request from an agent."""
        request_id = payload.get("request_id")

        if request_id:
            # Store the request
            self.pending_requests[request_id] = payload

            # Store routing info
            self.request_routing[request_id] = {
                "session_id": payload.get("session_id"),
                "api_input_id": api_input_id,
                "agent_name": payload.get("agent_name", "unknown")
            }

            # Broadcast to frontend
            await self._broadcast_to_frontend({
                "type": "inbox_update",
                "payload": {
                    "new_request": payload,
                    "total_pending": len(self.pending_requests)
                }
            })

            logger.info(f"New human input request: {request_id} from {api_input_id}")

    async def load_config_and_connect(self, config_path: str = "config/gui_config.yaml"):
        """Load configuration and connect to API inputs."""
        try:
            if Path(config_path).exists():
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)

                for api_input in config.get("api_inputs", []):
                    host = api_input["host"]
                    port = api_input["port"]
                    await self.connect_to_api_input(host, port)

                logger.info(f"Connected to {len(self.api_connections)} API inputs")
            else:
                logger.warning(f"Config file not found: {config_path}")
                logger.info("Attempting to connect to default API input on localhost:8000")
                try:
                    await self.connect_to_api_input("localhost", 8000)
                    logger.info("✅ Connected to default API input on port 8000")
                except Exception as e:
                    logger.warning(f"❌ Failed to connect to default API input: {e}")
                    logger.info("🔌 Running with no API input connections - events will not be received!")
                    logger.info("💡 Make sure the main woodwork agent system is running on port 8000")

        except Exception as e:
            logger.error(f"Failed to load config: {e}")

    async def start_server(self, host: str = "0.0.0.0", port: int = 3000):
        """Start the FastAPI GUI server."""
        # Connect to API inputs first
        await self.load_config_and_connect()

        # Start the server
        config = uvicorn.Config(
            app=self.app,
            host=host,
            port=port,
            log_level="info"
        )

        server = uvicorn.Server(config)
        logger.info(f"Starting FastAPI GUI server on {host}:{port}")
        await server.serve()


# Convenience function to start the server
async def start_gui_server():
    """Start the FastAPI GUI server."""
    server = FastAPIGUIServer()
    await server.start_server()


if __name__ == "__main__":
    asyncio.run(start_gui_server())