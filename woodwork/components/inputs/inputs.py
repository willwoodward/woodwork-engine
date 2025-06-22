from abc import abstractmethod

from woodwork.components.component import component
from woodwork.globals import global_config
from woodwork.helper_functions import format_kwargs


class inputs(component):
    def __init__(self, task_master, to, **config):
        format_kwargs(config, task_master=task_master, to=to, component="input")
        super().__init__(**config)

        self._task_master = task_master
        self._output = to

    def stop(self):
        self._task_master.close_all()
