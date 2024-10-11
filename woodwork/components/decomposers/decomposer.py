from abc import ABC, abstractmethod

from woodwork.components.component import component

class decomposer(component, ABC):
    def __init__(self, name, config):
        super().__init__(name, "decomposer")
        print("Creating the decomposer...")
        
        if not self._config_checker(name, ["tools", "output"], config): exit()

        self._tools = config["tools"]
        self._output = config["output"]
    
    @abstractmethod
    def input_handler(self, query):
        """Given a query, return the JSON array denoting the actions to take, passed to the task master."""
        pass
