import aiohttp
from typing import Optional
import logging

from woodwork.components.component import Component
from woodwork.deploy.deployment import Deployment
from woodwork.deploy.vms import LocalDeployment, ServerDeployment

log = logging.getLogger(__name__)


class DeploymentWrapper:
    def __init__(self, deployment: Deployment, component: Component):
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
            # Check if component has async process method (for streaming)
            if hasattr(self.component, "process"):
                result = self.component.process(data)
                # Handle both sync and async process methods
                if hasattr(result, "__await__"):  # asyncio.iscoroutine doesn't work with some coroutines
                    return await result
                return result
            else:
                # Fallback to input method
                return self.component.input(data)


class Router:
    def __init__(self):
        self.components: dict[str, DeploymentWrapper] = {}
        self.deployments: dict[str, Deployment] = {}

    def get(self, name) -> Optional[DeploymentWrapper]:
        return self.components.get(name)

    def add(self, component: Component, deployment=None):
        if deployment is None:
            deployment = LocalDeployment([component], name=str(hash(component)))

        self.components[component.name] = DeploymentWrapper(deployment, component)
        if deployment.name not in self.deployments:
            self.deployments[deployment.name] = deployment

    async def setup_streaming(self):
        """Set up stream managers for all streaming-enabled components.

        Streaming via StreamManager is disabled in the new architecture
        (message_bus was removed). This is a no-op kept for call-site compat.
        """
        log.debug("Router.setup_streaming: no-op in new architecture")


_router = None


def get_router():
    global _router
    if _router is None:
        _router = Router()
    return _router
