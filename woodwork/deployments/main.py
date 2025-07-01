import asyncio
import threading
import time

from woodwork.deployments.router import get_router


class Deployer:
    def __init__(self):
        self.router = get_router()

    def main(self):
        """
        Deploy all deployments that have been added to the router.
        """
        loop = asyncio.new_event_loop()
        threading.Thread(target=loop.run_forever, daemon=True).start()

        for deployment in self.router.deployments.values():
            asyncio.run_coroutine_threadsafe(deployment.deploy(), loop)

        # Block for a while to let them start
        time.sleep(1)
