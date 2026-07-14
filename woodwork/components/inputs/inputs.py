from abc import abstractmethod
import logging

from woodwork.components.component import Component
from woodwork.utils import format_kwargs

log = logging.getLogger(__name__)


class Input(Component):
    def __init__(self, to=None, **config):
        config.pop("task_master", None)
        if to is not None:
            config["to"] = to

        format_kwargs(config, to=to, type="component")
        super().__init__(**config)

        self._output = config.get("to")

    @abstractmethod
    def input_function(self):
        """Blocking call that returns one line of user input."""
        pass
