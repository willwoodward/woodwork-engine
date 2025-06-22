import logging
from threading import Thread

from typing import Any

from woodwork.components.component import component
from woodwork.helper_functions import format_kwargs
from woodwork.components.inputs.inputs import inputs
from woodwork.components.outputs.outputs import outputs

log = logging.getLogger(__name__)


class task_master(component):
    def __init__(self, **config):
        format_kwargs(config, component="task_master", type="default")
        super().__init__(**config)

    def add_tools(self, tools):
        self._tools = tools
        self._inputs = [component for component in tools if isinstance(component, inputs)]
        self._outputs = [component for component in tools if isinstance(component, outputs)]

    def execute(self, workflow: dict[str, Any]):
        log.debug("Executing instructions...")
        variables = {}
        prev_instructon = ""

        # Add the initial variables
        for key in workflow["inputs"]:
            variables[key] = workflow["inputs"][key]

        instructions = workflow["plan"]

        for instruction in instructions:
            # Substitute variable inputs
            for key in instruction["inputs"]:
                variable = str(instruction["inputs"][key])
                if variable in variables:
                    instruction["inputs"][key] = variables[variable]

            # Use tool
            result = self._use_tool(instruction)

            if not result:
                break

            # Add the result to the variables
            variables[instruction["output"]] = result
            prev_instructon = result  # TODO: @willwoodward fix spelling of variable if necessary
            log.debug(f"instruction = {instruction}")
            log.debug(f"result = {result}")

        return prev_instructon

    def _use_tool(self, instruction):
        try:
            result = None

            tool = list(filter(lambda x: x.name == instruction["tool"], self._tools))[0]
            result = tool.input(instruction["action"], instruction["inputs"])

            return result
        except:
            print("This instruction was not able to execute.")
            return

    def close_all(self):
        for tool in self._tools:
            if hasattr(tool, "close"):
                tool.close()

    def _loop(self, input_object: inputs):
        while True:
            x = input_object.input_function()

            if x == "exit" or x == ";":
                self.close_all()
                break

            # Traverse through outputs like a linked list
            obj = input_object
            if hasattr(obj, "_output") and obj._output is not None:
                while hasattr(obj, "_output") and obj._output is not None:
                    x = obj._output.input(x)
                    obj = obj._output

                # If the last object is not an output, print the result
                if not isinstance(obj, outputs):
                    print(x)

    def start(self):
        """Starts the input and output loops and orchestrates the execution of tasks."""
        # Currently only supports one input and output
        print('Input initialized, type ";" to exit.')
        thread = Thread(target=self._loop, args=(self._inputs[0],))
        thread.start()
