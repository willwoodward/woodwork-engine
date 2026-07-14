import logging

from woodwork.components.inputs.inputs import Input
from woodwork.utils import format_kwargs

log = logging.getLogger(__name__)


class CommandLineInput(Input):
    def __init__(self, **config):
        format_kwargs(config, type="command_line")
        super().__init__(**config)
        log.debug("Creating command line input...")

    def input_function(self):
        return input()

    def input(self):
        return self.input_function(self)
