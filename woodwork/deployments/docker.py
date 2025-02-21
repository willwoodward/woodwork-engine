import os
import docker
import io
import time

from woodwork.helper_functions import print_debug


class Docker:
    def __init__(
        self, image_name: str, container_name: str, dockerfile: str, container_args: dict, volume_location: str = None
    ):
        self.image_name = image_name
        self.container_name = container_name
        self.dockerfile = dockerfile
        self.container_args = container_args
        self.path = volume_location

        # Add the volume if its location is specified
        if volume_location is not None:
            self.container_args["volumes"] = (
                {
                    os.path.abspath(self.path): {
                        "bind": f"/{self.path.split("/")[-1]}",
                        "mode": "rw",
                    }
                },
            )

        self.docker_client = docker.from_env()

    def _ensure_data_directory(self):
        """Ensure the data directory exists."""
        if not os.path.exists(self.path):
            os.makedirs(self.path)
            print_debug(f"Created data directory at {self.path}")
        else:
            print_debug(f"Data directory already exists at {self.path}")

    def _build_docker_image(self):
        """Build the Docker image."""
        print_debug("Building Docker image...")

        self.docker_client.images.build(fileobj=io.BytesIO(self.dockerfile.encode("utf-8")), tag=self.image_name)
        print_debug(f"Successfully built image: {self.image_name}")

    def _run_docker_container(self):
        """Run the Docker container."""
        print_debug("Running Docker container...")

        # Check if the container already exists
        try:
            container = self.docker_client.containers.get(self.container_name)
            print_debug(f"Container '{self.container_name}' already exists. Starting it...")
            container.start()
        except docker.errors.NotFound:
            print_debug(f"Container '{self.container_name}' not found. Creating a new one...")
            self.docker_client.containers.run(
                self.image_name,
                name=self.container_name,
                detach=True,
                **self.container_args,
            )
            time.sleep(15)
        print_debug(f"Container '{self.container_name}' is running.")

    def init(self):
        if self.path is not None:
            self._ensure_data_directory()

        self._build_docker_image()
        self._run_docker_container()
