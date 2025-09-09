import asyncio
import logging
import json
import threading
import queue
from typing import Any, Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse

from woodwork.components.inputs.inputs import inputs
from woodwork.utils import format_kwargs
from woodwork.events import get_global_event_manager
from woodwork.types.events import PayloadRegistry
from woodwork.deployments.router import get_router

log = logging.getLogger(__name__)


class api_input(inputs):
    """API input component.

    Features (minimal, safe-to-import implementation):
    - Starts a FastAPI app when local=True by launching uvicorn in a background thread
      (uvicorn import/use is optional and only used when local=True).
    - Provides a WebSocket endpoint at /input which clients can connect to. Clients can
      send JSON messages with an "input" field to push an input into the engine. The
      same websocket receives broadcasted events from the global event manager.
    - Provides configurable REST routes (mapping path -> component_name) via the
      `routes` config dict. POSTing JSON to those routes will forward to the
      referenced component (using the router) and return the target's response.

    Notes about design choices:
    - Uses a thread-safe queue.Queue for incoming inputs so that the synchronous
      TaskMaster loop (which calls input_function synchronously) can block on
      queue.get(). REST handlers and websocket handlers put items into that queue.
    - Event broadcasting: registers synchronous event listeners for known event
      names (from PayloadRegistry) which push payload dicts into an internal queue.
      An asyncio task running in the FastAPI event loop consumes that queue and
      forwards messages to all connected WebSocket clients.
    """

    def __init__(self, **config):
        format_kwargs(config, type="api")
        super().__init__(**config)

        # Configuration
        self.local: bool = config.get("local", True)
        self.port: int = config.get("port", 8000)
        # routes: dict mapping endpoint path (no leading /) to component name
        # Example: {"ask": "agent1", "workflow/run": "workflow_runner"}
        self.routes: Dict[str, str] = config.get("routes", {})

        # Input queue used by the engine's synchronous input loop
        self._input_queue: queue.Queue = queue.Queue()

        # Event queue and websocket clients for broadcasting
        self._event_queue: queue.Queue = queue.Queue()
        self._websockets: List[WebSocket] = []

        # FastAPI app
        self.app = FastAPI()
        self._setup_routes()

        # Register synchronous event listeners to collect events
        self._register_event_listeners()

        # If running locally, start the server in background
        if self.local:
            try:
                import uvicorn

                thread = threading.Thread(target=self._run_uvicorn, daemon=True)
                thread.start()
            except Exception as e:
                log.warning(f"uvicorn not available or failed to start server: {e}")

    # Input API used by TaskMaster loop (synchronous)
    def input_function(self):
        # Block until an item is available
        value = self._input_queue.get()
        return value

    # External callers (REST / WS) use this to push inputs into the engine
    def push_input(self, value: Any):
        self._input_queue.put(value)

    # Internal: traverse outputs like TaskMaster._loop and push through router
    async def _forward_to_output(self, data: Any):
        router = get_router()
        component = self
        # If this component has an output, traverse and call deployment.input
        if hasattr(component, "_output") and component._output is not None:
            while hasattr(component, "_output") and component._output is not None:
                deployment = router.get(component._output.name)
                if deployment is None:
                    log.error(f"No deployment registered for {component._output.name}")
                    return None
                # DeploymentWrapper.input is async
                data = await deployment.input(data)
                component = component._output
            # If last object is not an output, return result
            return data
        else:
            # No output configured; just return the input value
            return data

    def _setup_routes(self):
        # Websocket endpoint for /input
        @self.app.websocket("/input")
        async def websocket_endpoint(ws: WebSocket):
            await ws.accept()
            self._websockets.append(ws)
            log.debug("WebSocket client connected to /input")
            try:
                # Keep listening for incoming messages from client
                while True:
                    data = await ws.receive_text()
                    try:
                        payload = json.loads(data)
                    except Exception:
                        payload = {"input": data}

                    # Prefer 'input' field if present
                    input_value = payload.get("input") if isinstance(payload, dict) else payload
                    # Push into engine (thread-safe)
                    self.push_input(input_value)
            except WebSocketDisconnect:
                log.debug("WebSocket client disconnected from /input")
                if ws in self._websockets:
                    self._websockets.remove(ws)

        # Dynamic REST routes based on self.routes
        for path, target in self.routes.items():
            route_path = f"/{path.strip('/') }"

            async def make_handler(request: Request, _target=target):
                try:
                    body = await request.json()
                except Exception:
                    body = await request.body()
                    try:
                        body = body.decode()
                    except Exception:
                        pass
                # If there is a routed component, call it via router
                router = get_router()
                deployment = router.get(_target)
                if deployment is None:
                    return JSONResponse({"error": f"No component named {_target} registered"}, status_code=404)
                # Forward payload to component via DeploymentWrapper.input
                result = await deployment.input(body)
                return JSONResponse({"result": result})

            # Register the route as POST
            self.app.post(route_path)(make_handler)

        # Startup event to launch broadcaster
        @self.app.on_event("startup")
        async def startup_event():
            # Launch async broadcaster task
            asyncio.create_task(self._event_broadcaster())

    def _register_event_listeners(self):
        # Register synchronous event listeners for known event names.
        # When invoked, listeners will push the payload dict into _event_queue.
        em = get_global_event_manager()
        for event_name in PayloadRegistry._registry.keys():
            # Define a closure to capture event_name
            def make_handler(name):
                def handler(payload):
                    try:
                        # payload may already be a typed payload object; try to convert
                        if hasattr(payload, "to_dict"):
                            data = payload.to_dict()
                        elif hasattr(payload, "to_json"):
                            data = json.loads(payload.to_json())
                        else:
                            data = payload
                        self._event_queue.put({"event": name, "payload": data})
                    except Exception as e:
                        log.exception(f"Failed to enqueue event for websocket broadcasting: {e}")

                return handler

            em.on_event(event_name, make_handler(event_name))

    async def _event_broadcaster(self):
        """Async task that forwards events from the thread-safe queue to websocket clients."""
        loop = asyncio.get_event_loop()
        while True:
            # Block in a threadpool until an event is available (queue.Queue.get)
            item = await loop.run_in_executor(None, self._event_queue.get)
            # Forward to all websockets (fire-and-forget to avoid blocking)
            disconnected = []
            for ws in list(self._websockets):
                try:
                    await ws.send_json(item)
                except Exception:
                    # Mark websocket for removal
                    disconnected.append(ws)
            for ws in disconnected:
                if ws in self._websockets:
                    self._websockets.remove(ws)

    def _run_uvicorn(self):
        try:
            import uvicorn

            # Use uvicorn programmatically; this call is blocking so run in a thread
            uvicorn.run(self.app, host="0.0.0.0", port=self.port, log_level="info")
        except Exception as e:
            log.exception(f"Failed to run uvicorn server: {e}")

    # Optional helper for clean-up if used
    def close(self):
        # No robust server shutdown provided here; rely on process exit
        log.debug("api_input.close() called")
