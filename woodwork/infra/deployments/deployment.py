from woodwork.helper_functions import format_kwargs
from woodwork.infra.infrastructure import Infrastructure


class Deployment(Infrastructure):
    """
    Base class for deployments.
    """

    def __init__(self, **config):
        """
        Initializes the deployment with deployment-essential parameters.
        """
        format_kwargs(config, component="deployment")
        super().__init__(**config)
