import logging
from threading import Thread
import asyncio
import json

from typing import Any

from woodwork.components.component import component
from woodwork.helper_functions import format_kwargs, get_optional
from woodwork.components.inputs.inputs import inputs
from woodwork.components.outputs.outputs import outputs
from woodwork.deployments.router import get_router
from woodwork.components.knowledge_bases.graph_databases.neo4j import neo4j
from woodwork.types import Workflow

log = logging.getLogger(__name__)


class task_master(component):
    def __init__(self, **config):
        format_kwargs(config, component="task_master", type="default")
        super().__init__(**config)

        # Setup workflows storage
        self.cache = neo4j(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="testpassword",
            name="decomposer_cache",
        )

        self._tools = []

    def add_tools(self, tools):
        self._tools = tools
        self._inputs = [component for component in tools if isinstance(component, inputs)]
        self._outputs = [component for component in tools if isinstance(component, outputs)]

    def execute(self, action: dict[str, Any]):
        """
        Executes a single action dictionary returned by the agent.
        """
        try:
            tool_name = action["tool"]
            action_name = action["action"]
            inputs = action.get("inputs", {})

            log.debug(f"Executing tool '{tool_name}' with action '{action_name}' and inputs {inputs}")

            # Find the tool object by name
            tool = next((t for t in self._tools if t.name == tool_name), None)
            if tool is None:
                raise ValueError(f"Tool '{tool_name}' not found.")

            # Call the tool's input method
            result = tool.input(action_name, inputs)
            log.debug(f"Tool result: {result}")
            return result

        except Exception as e:
            log.error(f"Failed to execute action: {e}")
            return None

    # def execute(self, workflow: dict[str, Any]):
    #     log.debug("Executing instructions...")
    #     variables = {}
    #     prev_instructon = ""

    #     # Add the initial variables
    #     for key in workflow["inputs"]:
    #         variables[key] = workflow["inputs"][key]

    #     instructions = workflow["plan"]

    #     for instruction in instructions:
    #         # Substitute variable inputs
    #         for key in instruction["inputs"]:
    #             variable = str(instruction["inputs"][key])
    #             if variable in variables:
    #                 instruction["inputs"][key] = variables[variable]

    #         # Use tool
    #         result = self._use_tool(instruction)

    #         if not result:
    #             break

    #         # Add the result to the variables
    #         variables[instruction["output"]] = result
    #         prev_instructon = result  # TODO: @willwoodward fix spelling of variable if necessary
    #         log.debug(f"instruction = {instruction}")
    #         log.debug(f"result = {result}")

    #     return prev_instructon

    # def _use_tool(self, instruction):
    #     try:
    #         result = None

    #         tool = list(filter(lambda x: x.name == instruction["tool"], self._tools))[0]
    #         result = tool.input(instruction["action"], instruction["inputs"])

    #         return result
    #     except:
    #         print("This instruction was not able to execute.")
    #         return

    def close_all(self):
        for tool in self._tools:
            if hasattr(tool, "close"):
                tool.close()

    async def _loop(self, input_object: inputs):
        router = get_router()
        while True:
            x = input_object.input_function()

            if x == "exit" or x == ";":
                self.close_all()
                break

            # Traverse through outputs like a linked list
            component = input_object
            if hasattr(component, "_output") and component._output is not None:
                while hasattr(component, "_output") and component._output is not None:
                    deployment = router.get(component._output.name)
                    x = await deployment.input(x)
                    component = component._output

                # If the last object is not an output, print the result
                if not isinstance(component, outputs):
                    print(x)

    def start(self):
        """Starts the input and output loops and orchestrates the execution of tasks."""
        # Currently only supports one input and output
        print('Input initialized, type ";" to exit.')

        def run():
            asyncio.run(self._loop(self._inputs[0]))

        thread = Thread(target=run)
        thread.start()
    
    def validate_workflow(self, workflow: Workflow, tools: list):
        # # Check tools exist
        # for action in workflow["plan"]:
        #     tool_names = list(map(lambda x: x.name, tools))

        #     if action["tool"] not in tool_names:
        #         raise SyntaxError("Tool not found.")
        return True

    def add_workflow(self, workflow: Workflow):
        self.validate_workflow(workflow, self._tools)
        id = self._cache_actions(workflow)
        print(f"Successfully added a new workflow with ID: {id}")
    
    def list_workflows(self):
        return self.cache.run(
            f"""MATCH (n:Prompt)-[:NEXT]->(m)
            RETURN n.value"""
        )

    def _cache_actions(self, workflow: dict[str, Any]):
        """Add the actions to the graph if they aren't already present, as a chain."""
        prompt = workflow["name"]
        workflow_inputs = str(list(workflow["inputs"].keys()))
        instructions = workflow["plan"]

        # # Check to see if the action has been cached
        # if self._cache_search_actions(prompt)["score"] > 0.96:
        #     log.debug("Similar prompts have already been cached.")
        #     return

        # Instructions must have at least one instruction
        if len(instructions) == 0:
            return

        # Generate the database query
        query = f'MERGE (p:Prompt {{value: "{prompt}", inputs: {workflow_inputs}}})'

        for instruction in instructions:
            query += f'-[:NEXT]->(:Action {{value: "{instruction}"}})'

        query += "\nRETURN elementId(p) as id"

        # Execute query
        result = self.cache.run(query)[0]

        # Add the vector embedding for the prompt
        # self._cache.embed("Prompt", "value")

        # Return the ID of the prompt node
        # return result["id"]
        return None