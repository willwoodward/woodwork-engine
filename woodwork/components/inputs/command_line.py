from threading import Thread

from woodwork.helper_functions import print_debug
from woodwork.components.inputs.inputs import inputs


class command_line(inputs):
    def __init__(self, name, **config):
        super().__init__(name, **config)
        print_debug("Creating command line input...")
        print('Command line input initialised, type ";" to exit. Begin typing a message:')

        thread = Thread(target=self.__input_loop)
        thread.start()

    def __input_loop(self):
        while True:
            x = input()

            if x == "exit" or x == ";":
                break

            # Send the input to the component
            print(self._output.input(x))
