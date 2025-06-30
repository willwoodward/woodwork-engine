import inspect
import aiohttp
from fastapi import FastAPI, Request
from uvicorn import Config, Server
from typing import List, Optional

from woodwork.components.component import component


class Deployment():
    def __init__(self, components: List[component]):
        self.components = components
    

class LocalDeployment(Deployment):
    def __init__(self, components: List[component]):
        super().__init__(components)
    
    async def deploy(self):
        return

class ServerDeployment(Deployment):
    def __init__(self, components: List[component], port=None):
        self.app = FastAPI()
        self.port = port
        super().__init__(components)
        self._register_routes()

    def _register_routes(self):
        for component in self.components:
            @self.app.post(f"/{component.name}/input")
            async def input(request: Request):
                data = await request.json()
                return await self._maybe_async(component.input, data["value"])

    async def _maybe_async(self, func, *args, **kwargs):
        if inspect.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)

    async def deploy(self):
        config = Config(app=self.app, host="0.0.0.0", port=self.port, loop="asyncio", log_level="critical", access_log=True)
        server = Server(config)
        await server.serve()

class DeploymentWrapper:
    def __init__(self, deployment: Deployment, component: component):
        self.deployment = deployment
        self.component = component

    async def input(self, data):
        if isinstance(self.component, ServerDeployment):
            async with aiohttp.ClientSession() as session:
                async with session.post(f"http://0.0.0.0:{self.component.name}/{self.component.port}/input", json={"value": str(data)}) as response:
                    print("SERVER")
                    return await response.text()
        else:
            return self.component.input(data)

class Router:
    def __init__(self):
        self.components: dict[str, DeploymentWrapper] = {}

    def get(self, name) -> Optional[DeploymentWrapper]:
        return self.components.get(name)
    
    def add(self, component: component, deployment=None):
        if isinstance(deployment, ServerDeployment):
            self.components[component.name] = DeploymentWrapper(deployment, component)
            return
        self.components[component.name] = DeploymentWrapper(LocalDeployment([component]), component)
