import logging
from threading import Thread

from woodwork.components.inputs.inputs import inputs
from woodwork.helper_functions import format_kwargs

log = logging.getLogger(__name__)


class command_line(inputs):
    def __init__(self, **config):
        format_kwargs(config, type="command_line")
        super().__init__(**config)
        log.debug("Creating command line input...")

        if self._is_running:
            print('Command line input initialized, type ";" to exit. Begin typing a message:')

            thread = Thread(target=self.__input_loop)
            thread.start()

    def __input_loop(self):
        while True:
            x = input()

            if x == "exit" or x == ";":
                self.stop()
                break

            # Send the input to the component
            self._output.input(x)
