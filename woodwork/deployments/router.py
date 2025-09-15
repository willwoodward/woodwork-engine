import aiohttp
from typing import Optional
import logging

from woodwork.components.component import component
from woodwork.deployments.deployment import Deployment
from woodwork.deployments.vms import LocalDeployment, ServerDeployment

log = logging.getLogger(__name__)


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
            # Check if component has async process method (for streaming)
            if hasattr(self.component, 'process'):
                result = self.component.process(data)
                # Handle both sync and async process methods
                if hasattr(result, '__await__'):  # asyncio.iscoroutine doesn't work with some coroutines
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

    def add(self, component: component, deployment=None):
        if deployment is None:
            deployment = LocalDeployment([component], name=str(hash(component)))

        self.components[component.name] = DeploymentWrapper(deployment, component)
        if deployment.name not in self.deployments:
            self.deployments[deployment.name] = deployment
    
    async def setup_streaming(self):
        """Set up stream managers for all streaming-enabled components"""
        from woodwork.core.simple_message_bus import get_global_message_bus
        from woodwork.core.stream_manager import StreamManager
        
        try:
            # Get global message bus and stream manager
            message_bus = await get_global_message_bus()
            stream_manager = StreamManager(message_bus)
            await stream_manager.start()
            
            # Set stream manager for all streaming components
            streaming_count = 0
            for component_wrapper in self.components.values():
                component = component_wrapper.component
                if hasattr(component, 'streaming_enabled') and component.streaming_enabled:
                    if hasattr(component, 'set_stream_manager'):
                        component.set_stream_manager(stream_manager)
                        streaming_count += 1
                        log.debug(f"✅ Set up streaming for component: {component.name}")
                    else:
                        log.debug(f"❌ Component {component.name} has streaming enabled but no set_stream_manager method")
            
            log.debug(f"Router set up streaming for {streaming_count} components")
            
            return stream_manager
            
        except Exception as e:
            log.error(f"Error setting up streaming: {e}")
            return None


_router = None


def get_router():
    global _router
    if _router is None:
        _router = Router()
    return _router
