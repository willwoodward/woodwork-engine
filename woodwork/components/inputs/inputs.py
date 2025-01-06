from abc import abstractmethod

from woodwork.components.component import component


class inputs(component):
    def __init__(self, name, to, **config):
        super().__init__(name, "input")

        self._output = to

    @abstractmethod
    def __input_handler(self):
        """Starts a thread which runs this function, sending the input to the task manager and returning the result."""
        pass
