import requests

from woodwork.components.apis.api import api

class web(api):
    def __init__(self, name, config):
        print("Configuring API...")
        self.__url = config["url"]
        
        super().__init__(name, config)
        print("API configured.")

    def call(self, req):
        res = requests.get(f"http://127.0.0.1:5000/{req}")
        return res.text