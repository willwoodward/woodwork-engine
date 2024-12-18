import requests
import os

from woodwork.helper_functions import print_debug
from woodwork.components.apis.api import api

class web(api):
    def __init__(self, name, config):
        print_debug("Configuring API...")
        self.__url = config["url"]
        
        super().__init__(name, config)
        
        # Ingest the API documentation
        if "documentation" in config:
            with open (os.getcwd() + "/" + config["documentation"]) as f:
                self._documentation = f.read()
        
        print_debug("API configured.")

    def input(self, req: str, inputs: dict):
        res = requests.get(f"http://127.0.0.1:3000/{req}", params=inputs)
        return res.text
    
    @property
    def description(self): return self._documentation