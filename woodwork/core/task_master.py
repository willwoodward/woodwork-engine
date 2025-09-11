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
from woodwork.core.stream_manager import StreamManager

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
            name="agent_cache",
        )

        self._tools = []
        self._inputs = []
        self._outputs = []
        self.workflow_name: Optional[str] = None
        self.workflow_actions: dict[str, Action] = {}
        self.workflow_variables: dict[str, Any] = {}
        self.last_action_name: str = None

    def add_tools(self, tools):
        self._tools = self._tools + tools
        self._inputs = self._inputs + [component for component in tools if isinstance(component, inputs)]
        self._outputs = self._outputs + [component for component in tools if isinstance(component, outputs)]

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

            result = None
            if action.tool == "ask_user":
                result = input(f"{action.inputs["question"]}\n")
            else:
                tools = list(filter(lambda t: t.name == action.tool, self._tools))
                if len(tools) == 0:
                    raise ValueError(f"Tool '{action.tool}' not found.")
                tool = tools[0]

                result = tool.input(action.action, action.inputs)
                log.debug(f"Tool result: {result}")

            self.workflow_actions[action.output] = action
            self.workflow_variables[action.output] = result
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
    
    async def _handle_console_output(self, data: Any):
        """Handle output to console, with streaming support"""
        log.debug(f"TaskMaster handling console output: {data}")
        if isinstance(data, str) and data.startswith("stream:"):
            log.debug("TaskMaster detected streaming output, handling as stream")
            await self._handle_streaming_console_output(data)
        else:
            # Regular non-streaming output
            log.debug("TaskMaster handling as regular non-streaming output")
            print(data)
    
    async def _handle_streaming_console_output(self, stream_data: str):
        """Handle streaming output to console"""
        try:
            # Check if stream manager is available
            if not hasattr(self, '_stream_manager') or self._stream_manager is None:
                log.error("TaskMaster: No stream manager available for console output")
                print(f"\nNo stream manager available. Output: {stream_data}")
                return
            
            # Extract stream ID
            stream_id = stream_data.replace("stream:", "")
            log.debug(f"TaskMaster extracting stream ID: {stream_id}")
            
            # Give a tiny moment for the stream to be set up
            await asyncio.sleep(0.001)
            
            # Stream output to console
            log.debug(f"TaskMaster starting to receive stream chunks for {stream_id}")
            chunk_count = 0
            async for chunk in self._stream_manager.receive_stream(stream_id):
                chunk_count += 1
                log.debug(f"TaskMaster received chunk {chunk_count}: '{chunk.data}'")
                print(chunk.data, end="", flush=True)
            
            print()  # New line at the end
            log.debug(f"TaskMaster finished streaming {chunk_count} chunks for {stream_id}")
            
        except Exception as e:
            log.error(f"TaskMaster streaming error: {e}")
            print(f"\nError handling streaming output: {e}")
            # Fallback to regular output
            print(stream_data)

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

                # If the last object is not an output, handle console output
                if not isinstance(component, outputs):
                    await self._handle_console_output(x)

    def start(self):
        """Starts the input and output loops and orchestrates the execution of tasks."""
        # Currently only supports one input and output
        print('Input initialized, type ";" to exit.')

        def run():
            # Create and set a persistent event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._async_start())
            finally:
                # Clean up pending tasks before closing
                pending = asyncio.all_tasks(loop)
                if pending:
                    log.debug(f"Cancelling {len(pending)} pending tasks")
                    for task in pending:
                        task.cancel()
                    # Wait for cancellation to complete
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.close()

        thread = Thread(target=run)
        thread.start()
    
    async def _async_start(self):
        """Async startup to handle streaming setup"""
        # Set up streaming for all components
        router = get_router()
        stream_manager = await router.setup_streaming()
        if stream_manager:
            log.debug("TaskMaster: Streaming set up successfully")
            # Store the same stream manager instance for console output
            self._stream_manager = stream_manager
        else:
            log.warning("TaskMaster: Failed to set up streaming")
        
        # Start the main loop
        await self._loop(self._inputs[0])

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
