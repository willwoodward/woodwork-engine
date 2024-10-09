from abc import ABC, abstractmethod

from woodwork.components.component import component

class inputs(component):
    def __init__(self, name, config):
        super().__init__(name, "input")
        
        if not self._config_checker(name, ["to"], config): exit()

        self._output = config["to"]

    @abstractmethod
    def __input_handler(self):
        """Starts a thread which runs this function, sending the input to the task manager and returning the result."""
        pass