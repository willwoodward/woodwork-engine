from abc import abstractmethod
import logging

from woodwork.components.component import component
from woodwork.utils import format_kwargs

log = logging.getLogger(__name__)


class inputs(component):
    def __init__(self, to=None, **config):
        # Remove task_master from config if passed (legacy support)
        config.pop("task_master", None)
        if to is not None:
            config["to"] = to

        format_kwargs(config, to=to, type="component")
        super().__init__(**config)

        self._output = config.get("to")

    def _can_stream_input(self) -> bool:
        """Input components typically don't receive streams"""
        return False

    def _can_stream_output(self) -> bool:
        """Input components can stream output if configured"""
        return True

    @abstractmethod
    def input_function(self):
        """The function that will be run in a separate thread to handle input."""
        pass
