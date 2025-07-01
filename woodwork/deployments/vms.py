from typing import List
import inspect
from fastapi import FastAPI, Request
from uvicorn import Config, Server

from woodwork.components.component import component
from woodwork.deployments.deployment import Deployment
from woodwork.helper_functions import format_kwargs


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
