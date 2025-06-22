from abc import abstractmethod

from woodwork.components.component import component
from woodwork.helper_functions import format_kwargs


class inputs(component):
    def __init__(self, task_master, to, **config):
        format_kwargs(config, task_master=task_master, to=to, component="input")
        super().__init__(**config)

        self._task_master = task_master
        self._output = to

    def stop(self):
        self._task_master.close_all()

    @abstractmethod
    def input_function(self):
        """The function that will be run in a separate thread to handle input."""
        pass
