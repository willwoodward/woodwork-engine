import asyncio
import inspect
from types import SimpleNamespace

class Route:
    def __init__(self, path, methods, handler):
        self.path = path
        self.methods = methods
        self.endpoint = handler

class FastAPI:
    def __init__(self, *args, **kwargs):
        self.routes = []
        self._handlers = {}  # key: (method, path)

    def add_route(self, path, methods, handler):
        # store handler; wrap async handlers to run in separate thread to avoid nested loop issues
        if asyncio.iscoroutinefunction(handler):
            def sync_handler(request):
                import threading
                result = {}
                def target():
                    try:
                        res = asyncio.run(handler(request))
                        result['res'] = res
                    except Exception as e:
                        result['res'] = e
                t = threading.Thread(target=target)
                t.start()
                t.join()
                if isinstance(result['res'], Exception):
                    raise result['res']
                return result['res']
            stored = sync_handler
        else:
            stored = handler

        self._handlers[(methods[0].upper(), path)] = stored
        self.routes.append(Route(path, methods, stored))

    def post(self, path):
        def decorator(func):
            self.add_route(path, ["POST"], func)
            return func
        return decorator

    def get(self, path):
        def decorator(func):
            self.add_route(path, ["GET"], func)
            return func
        return decorator

    def websocket(self, path):
        # For tests we don't need real websocket behavior; just register
        def decorator(func):
            # register as a websocket route for introspection
            self.routes.append(Route(path, ["WS"], func))
            return func
        return decorator

    def add_middleware(self, *args, **kwargs):
        # no-op for stub
        return None

# Minimal Request and WebSocket stubs
class Request:
    def __init__(self, json_data=None):
        self._json_data = json_data or {}

    async def json(self):
        return self._json_data

class WebSocketDisconnect(Exception):
    pass

class WebSocket:
    async def accept(self):
        return None
    async def send_json(self, payload):
        return None
    async def receive_text(self):
        return ""

# Provide nested modules via simple namespaces
responses = SimpleNamespace()

# JSONResponse compatible with tests
class JSONResponse:
    def __init__(self, content=None, status_code: int = 200):
        self.content = content or {}
        self.status_code = status_code

    def json(self):
        return self.content

responses.JSONResponse = JSONResponse

# Expose commonly referenced names
__all__ = ["FastAPI", "WebSocket", "WebSocketDisconnect", "Request", "responses"]

# Provide a testclient module importable as fastapi.testclient
from . import testclient  # noqa
