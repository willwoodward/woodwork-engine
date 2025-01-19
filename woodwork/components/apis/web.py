import requests
import os

from woodwork.helper_functions import print_debug, format_kwargs
from woodwork.components.apis.api import api


class web(api):
    def __init__(self, url: str, **config):
        format_kwargs(config, url=url, type="web")
        super().__init__(**config)
        print_debug("Configuring API...")

        self._url = url

        # Ingest the API documentation
        if "documentation" in config:
            with open(os.getcwd() + "/" + config["documentation"]) as f:
                self._documentation = f.read()

        self._documentation += "Call the endpoints by specifying just the endpoint name as the action, and the parameters as a dictionary in inputs."

        print_debug("API configured.")

    def input(self, req: str, inputs: dict):
        res = requests.get(f"http://{self._url}/{req}", params=inputs)
        return res.text

    @property
    def description(self):
        return self._documentation
