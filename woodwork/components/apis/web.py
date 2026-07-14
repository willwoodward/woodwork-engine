import logging
import os

import requests

from woodwork.components.apis.api import API
from woodwork.utils import format_kwargs

log = logging.getLogger(__name__)


class Web(API):
    def __init__(self, url: str, **config):
        format_kwargs(config, url=url, type="web")
        super().__init__(**config)
        log.debug("Configuring Web API...")

        self._url = url
        self._documentation = ""
        if "documentation" in config:
            with open(os.getcwd() + "/" + config["documentation"]) as f:
                self._documentation = f.read()

        self._documentation += (
            "Call the endpoints by specifying just the endpoint name as the action, "
            "and the parameters as a dictionary in inputs."
        )
        log.debug("Web API configured.")

    def execute(self, req: str, inputs: dict) -> str:
        res = requests.get(f"http://{self._url}/{req}", params=inputs)
        return res.text

    # Legacy alias
    def input(self, req: str, inputs: dict) -> str:
        return self.execute(req, inputs)

    @property
    def description(self):
        return self._documentation
