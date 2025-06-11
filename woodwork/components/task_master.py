import logging

from typing import Any

from woodwork.components.component import component
from woodwork.helper_functions import format_kwargs

log = logging.getLogger(__name__)


class task_master(component):
    def __init__(self, **config):
        format_kwargs(config, component="task_master", type="default")
        super().__init__(**config)

    def add_tools(self, tools):
        self._tools = tools

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
