import inspect
import aiohttp
from fastapi import FastAPI, Request
from uvicorn import Config, Server
from typing import List, Optional

from woodwork.components.component import component
from woodwork.helper_functions import format_kwargs


class Deployment:
    def __init__(self, name: str, components: List[component], **config):
        self.name = name
        self.components = components


class LocalDeployment(Deployment):
    def __init__(self, components: List[component], **config):
        format_kwargs(config, components=components)
        super().__init__(**config)

    async def deploy(self):
        return


class ServerDeployment(Deployment):
    def __init__(self, components: List[component], port=43001, **config):
        format_kwargs(config, components=components, port=port)
        super().__init__(**config)
        self.app = FastAPI()
        self.port = port
        self._register_routes()

    def _register_routes(self):
        for comp in self.components:

            @self.app.post(f"/{comp.name}/input")
            async def input(request: Request):
                data = await request.json()
                return await self._maybe_async(comp.input, data["value"])

    async def _maybe_async(self, func, *args, **kwargs):
        if inspect.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)

    async def deploy(self):
        config = Config(
            app=self.app, host="0.0.0.0", port=self.port, loop="asyncio", log_level="critical", access_log=True
        )
        server = Server(config)
        await server.serve()


class DeploymentWrapper:
    def __init__(self, deployment: Deployment, component: component):
        self.deployment = deployment
        self.component = component

    async def input(self, data):
        if isinstance(self.deployment, ServerDeployment):
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"http://0.0.0.0:{self.deployment.port}/{self.component.name}/input", json={"value": str(data)}
                ) as response:
                    resp = await response.text()
                    return resp[1:-1]
        else:
            return self.component.input(data)


class Router:
    def __init__(self):
        self.components: dict[str, DeploymentWrapper] = {}
        self.deployments: dict[str, Deployment] = {}

    def get(self, name) -> Optional[DeploymentWrapper]:
        return self.components.get(name)

    def add(self, component: component, deployment=None):
        if deployment is None:
            deployment = LocalDeployment([component], name=str(hash(component)))
        
        self.components[component.name] = DeploymentWrapper(deployment, component)
        if deployment.name not in self.deployments:
            self.deployments[deployment.name] = deployment


_router = None


def get_router():
    global _router
    if _router is None:
        _router = Router()
    return _router
