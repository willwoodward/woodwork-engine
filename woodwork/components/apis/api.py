import os

from woodwork.components.component import component

class api(component):
    def __init__(self, name, config):
        # Ingest the API documentation
        if "documentation" in config:
            with open (os.getcwd() + "/" + config["documentation"]) as f:
                self.__documentation = f.read()
        
        super().__init__(name, "api")
        

    
    def describe(self):
        return self.__documentation