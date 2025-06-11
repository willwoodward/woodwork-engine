import io
import logging
import os
import time

import docker
from docker.errors import NotFound

log = logging.getLogger(__name__)


class Docker:
    def __init__(
        self,
        image_name: str,
        container_name: str,
        dockerfile: str,
        container_args: dict,
        volume_location: str | None = None,
    ):
        self.image_name = image_name
        self.container_name = container_name
        self.dockerfile = dockerfile
        self.container_args = container_args
        self.path = volume_location

        # Add the volume if its location is specified
        if volume_location is not None:
            self.container_args["volumes"] = {
                os.path.abspath(self.path): {
                    "bind": f"/{self.path.split('/')[-1]}",
                    "mode": "rw",
                }
            }

        self.docker_client = docker.from_env()

    def _ensure_data_directory(self):
        """Ensure the data directory exists."""
        if not os.path.exists(self.path):
            os.makedirs(self.path)
            log.debug(f"Created data directory at {self.path}")
        else:
            log.debug(f"Data directory already exists at {self.path}")

    def _build_docker_image(self):
        """Build the Docker image."""

        log.debug("Building Docker image...")
        self.docker_client.images.build(fileobj=io.BytesIO(self.dockerfile.encode("utf-8")), tag=self.image_name)
        log.debug(f"Successfully built image: {self.image_name}")

    def _run_docker_container(self):
        """Run the Docker container."""
        log.debug("Running Docker container...")

        # Check if the container already exists
        container = None
        try:
            container = self.docker_client.containers.get(self.container_name)
            log.debug(f"Container '{self.container_name}' already exists. Starting it...")
            container.start()
            self.container = container
            time.sleep(10)
            self.wait_for_container(container)
        except NotFound:
            log.debug(f"Container '{self.container_name}' not found. Creating a new one...")
            container = self.docker_client.containers.run(
                self.image_name,
                name=self.container_name,
                detach=True,
                **self.container_args,
            )
            self.wait_for_container(container)
            self.container = container
        log.debug(f"Container '{self.container_name}' is running.")
        return container

    def wait_for_container(self, container, timeout=60):
        start_time = time.time()
        while time.time() - start_time < timeout:
            container.reload()  # Refresh container state
            if container.status == "running":
                return True
            time.sleep(0.5)
        raise TimeoutError(f"Timeout: Container {container.name} did not start in {timeout} seconds.")

    def get_container(self):
        return self.container

    def close(self):
        log.debug(f"Stopping container {self.container.name}...")
        self.container.stop()

    def init(self):
        if self.path is not None:
            self._ensure_data_directory()

        self._build_docker_image()
        self._run_docker_container()
