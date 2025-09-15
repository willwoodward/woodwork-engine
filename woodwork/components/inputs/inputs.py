from abc import abstractmethod
import logging

from woodwork.components.component import component
from woodwork.utils import format_kwargs

log = logging.getLogger(__name__)


class inputs(component):
    def __init__(self, task_master=None, to=None, **config):
        # Handle both old (task_master, to) and new (unified config) signatures
        if task_master is not None:
            config["task_master"] = task_master
        if to is not None:
            config["to"] = to
        
        print(f"to: {to}")

        format_kwargs(config, task_master=task_master, to=to, type="component")
        super().__init__(**config)

        self._task_master = config.get("task_master")
        self._output = config.get("to")
    
    def _can_stream_input(self) -> bool:
        """Input components typically don't receive streams"""
        return False
    
    def _can_stream_output(self) -> bool:
        """Input components can stream output if configured"""
        return True

    def stop(self):
        self._task_master.close_all()

    @abstractmethod
    def input_function(self):
        """The function that will be run in a separate thread to handle input."""
        pass
