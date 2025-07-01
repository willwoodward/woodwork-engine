import asyncio
import multiprocessing
import threading
import time
from typing import Optional

from woodwork.types import Update
from woodwork.deployments.router import get_router


class Deployer:
    def __init__(self):
        self.router = get_router()
        self.timeout = 0.1
        self.retries = 100

    def main(self):
        """
        Deploy all deployments that have been added to the router.
        """
        loop = asyncio.new_event_loop()
        threading.Thread(target=loop.run_forever, daemon=True).start()

        for deployment in self.router.deployments.values():
            asyncio.run_coroutine_threadsafe(deployment.deploy(), loop)

    def healthy(self, queue: Optional[multiprocessing.Queue] = None):
        """
        Wait for all deployments to be healthy and update the queue with the status of each component.
        :param queue: Optional multiprocessing queue to send updates to.
        """
        # Wait for all deployments to be healthy
        component_healthy = {component_name: False for component_name in self.router.components}
        deployment_healthy = {deployment_name: False for deployment_name in self.router.deployments}
        for _ in range(self.retries):
            for deployment_name in self.router.deployments:
                if deployment_healthy[deployment_name]:
                    continue
                if self.router.deployments[deployment_name].is_healthy():
                    deployment_healthy[deployment_name] = True
                    for component in self.router.deployments[deployment_name].components:
                        component_healthy[component.name] = True

                        if queue is not None:
                            print(f"Component {component.name} is healthy")
                            queue.put(Update(33, component.name))

            if all(deployment_healthy.values()):
                break
            time.sleep(self.timeout)
