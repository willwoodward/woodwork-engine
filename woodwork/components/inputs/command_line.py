import logging

from woodwork.components.inputs.inputs import inputs
from woodwork.helper_functions import format_kwargs

log = logging.getLogger(__name__)


class command_line(inputs):
    def __init__(self, **config):
        format_kwargs(config, type="command_line")
        super().__init__(**config)
        log.debug("Creating command line input...")

    def input_function(self):
        return input()
