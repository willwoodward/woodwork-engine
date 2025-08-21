import logging
from threading import Thread
import asyncio

from typing import Any, Optional

from woodwork.components.component import component
from woodwork.utils import format_kwargs
from woodwork.components.inputs.inputs import inputs
from woodwork.components.outputs.outputs import outputs
from woodwork.deployments.router import get_router
from woodwork.components.knowledge_bases.graph_databases.neo4j import neo4j
from woodwork.types import Action, Workflow

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
        self.workflow_name: Optional[str] = None
        self.workflow_actions: dict[str, Action] = {}
        self.workflow_variables: dict[str, Any] = {}
        self.last_action_name: str = None

    def add_tools(self, tools):
        self._tools = tools
        self._inputs = [component for component in tools if isinstance(component, inputs)]
        self._outputs = [component for component in tools if isinstance(component, outputs)]

    def start_workflow(self, workflow_name: str):
        """
        Initialises a new workflow collection to track workflow.
        """
        self.workflow_name = workflow_name

    def end_workflow(self):
        """
        Triggers a clean-up of unhelpful actions.
        """
        # logic to clean actions
        print(self.workflow_actions)
        self.workflow_actions = {}
        self.workflow_variables = {}

    def execute(self, action: Action):
        """
        Executes a single action returned by the agent.
        """
        try:
            # Substitute variable inputs
            for key in action.inputs:
                variable = str(action.inputs[key])
                if variable in self.workflow_variables:
                    action.inputs[key] = self.workflow_variables[variable]

            log.debug(f"Executing tool '{action.tool}' with action '{action.action}' and inputs {action.inputs}")

            tools = list(filter(lambda t: t.name == action.tool, self._tools))
            if len(tools) == 0:
                raise ValueError(f"Tool '{action.tool}' not found.")
            tool = tools[0]

            result = tool.input(action.action, action.inputs)
            log.debug(f"Tool result: {result}")

            self.workflow_actions[action.output] = action
            self.workflow_variables = result
            self.last_action_name = action.output
            return result

        except Exception as e:
            log.error(f"Failed to execute action: {e}")
            return None

    def cache_add_action(self, action: Action):
        dependencies = [var for var in action.inputs.values() if var in self.workflow_variables]
        if len(dependencies) == 0:
            self.cache.run(
                f"""MERGE (p:Prompt)-[:NEXT]->(:Action {{value: "{action.to_dict()}"}})
                WHERE p.name = {self.workflow_name}"""
            )
        else:
            self.cache.run(
                """
                MATCH (prompt:Prompt {name: $prompt_name})
                MATCH (target:Action {name: $action_name})
                MATCH path=(prompt)-[:NEXT*]->(target)
                WITH target
                MATCH (dep:Dependency {name: $new_name})
                MERGE (target)-[:DEPENDS_ON]->(dep)
                """
            )

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
        return True

    def list_workflows(self):
        result = self.cache.run(
            """MATCH (n:Prompt)-[:NEXT]->(m)
            RETURN n.value"""
        )
        return list(map(lambda x: x["n.value"], result))

    def _cache_actions(self, workflow: Workflow):
        """Add the actions to the graph if they aren't already present, as a chain."""
        prompt = workflow.name
        workflow_inputs = str(list(workflow.inputs.keys()))
        instructions = workflow.plan

        if len(instructions) == 0:
            return

        # Check to see if the action has been cached
        if self._cache_search_actions(prompt)["score"] > 0.97:
            log.debug("Similar prompts have already been cached.")
            return

        # Generate the database query
        query = f'MERGE (p:Prompt {{value: "{prompt}", inputs: {workflow_inputs}}})'

        for instruction in instructions:
            query += f'-[:NEXT]->(:Action {{value: "{instruction}"}})'

        query += "\nRETURN elementId(p) as id"

        # Execute query
        result = self.cache.run(query)[0]

        # Add the vector embedding for the prompt
        self.cache.embed("Prompt", "value")

        # Return the ID of the prompt node
        return result["id"]
