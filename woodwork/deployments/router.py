import aiohttp
from typing import Optional

from woodwork.components.component import component
from woodwork.deployments.deployment import Deployment
from woodwork.deployments.vms import LocalDeployment, ServerDeployment


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
        print(self.components, name)
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
