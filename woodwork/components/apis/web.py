import requests
import json 

from woodwork.components.apis.api import api

class web(api):
    def __init__(self, name, config):
        print("Configuring API...")
        self.__url = config["url"]
        
        super().__init__(name)
        print("API configured.")

    def call(self, req):
        res = requests.get(f"{self.__url}/{req}")
        return json.loads(res.text)