from woodwork.infra.deployments.deployment import Deployment
from woodwork.helper_functions import format_kwargs


class DockerDeployment(Deployment):
    """
    A class to handle Docker deployments for Woodwork.
    """

    def __init__(self, **config):
        """
        Initializes the Docker deployment with the specified image name.
        """
        format_kwargs(config, type="docker")
        super().__init__(**config)

    def deploy(self):
        """
        Deploys the Woodwork application using Docker.
        """
        raise NotImplementedError("Docker deployment logic is not implemented yet.")
