from abc import abstractmethod

from woodwork.components.component import component
from woodwork.globals import global_config
from woodwork.helper_functions import format_kwargs


class inputs(component):
    def __init__(self, to, **config):
        format_kwargs(config, to=to, component="input")
        super().__init__(**config)

        self._output = to
        self._is_running = global_config["inputs_activated"]

    @abstractmethod
    def __input_handler(self):
        """Starts a thread which runs this function, sending the input to the task manager and returning the result."""
        pass
