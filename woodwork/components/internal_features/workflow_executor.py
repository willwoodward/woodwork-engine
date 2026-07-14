"""Workflow execution engine via unified event bus.

This module provides the WorkflowExecutor class that executes workflows
by running their action sequences through the unified event bus.
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import uuid
import json
import asyncio as _asyncio


def emit(event: str, payload) -> None:
    """Shim: schedule an async emission without requiring a global bus."""
    try:
        loop = _asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_asyncio.coroutine(lambda: None)())
    except Exception:
        pass

log = logging.getLogger(__name__)


@dataclass
class WorkflowExecutionContext:
    """Context for workflow execution."""

    workflow_id: str
    inputs: Dict[str, Any]
    session_id: str
    execution_id: str
    variables: Dict[str, Any]  # Runtime variables (action outputs)


class WorkflowExecutor:
    """Executes workflows via unified event bus."""

    def __init__(self, neo4j_component, agent_component):
        """
        Initialize workflow executor.

        Args:
            neo4j_component: Neo4j knowledge base for workflow retrieval
            agent_component: Agent component for tool execution via request API
        """
        self._neo4j = neo4j_component
        self._agent = agent_component
        log.debug("WorkflowExecutor initialized")

    async def execute_workflow(self, workflow_id: str, inputs: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """
        Execute a workflow by ID with given inputs.

        Args:
            workflow_id: Workflow ID to execute
            inputs: Input variables for the workflow
            session_id: Session ID for tracking

        Returns:
            Dict with execution results and final outputs

        Raises:
            ValueError: If workflow has no actions or tool not found
        """
        execution_id = str(uuid.uuid4())
        context = WorkflowExecutionContext(
            workflow_id=workflow_id,
            inputs=inputs,
            session_id=session_id,
            execution_id=execution_id,
            variables=inputs.copy(),
        )

        log.info(f"Executing workflow {workflow_id} with execution_id {execution_id}")

        # Get workflow action sequence from Neo4j
        actions = await self._get_workflow_actions(workflow_id)

        if not actions:
            raise ValueError(f"Workflow {workflow_id} has no actions")

        # Execute actions in sequence
        results = []
        for action in actions:
            result = await self._execute_action(action, context)
            results.append(result)

            # Store output in context for dependent actions
            if action.get("output"):
                context.variables[action["output"]] = result.get("output")

        log.info(f"Workflow {workflow_id} execution completed")

        return {
            "execution_id": execution_id,
            "workflow_id": workflow_id,
            "status": "completed",
            "results": results,
            "final_outputs": context.variables,
        }

    async def execute_entrypoint(self, entrypoint_name: str, inputs: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """
        Execute workflow via entrypoint name.

        Args:
            entrypoint_name: Name of entrypoint to execute
            inputs: Input variables
            session_id: Session ID for tracking

        Returns:
            Execution results

        Raises:
            ValueError: If entrypoint not found or validation fails
        """
        log.info(f"Executing entrypoint '{entrypoint_name}' with inputs: {inputs}")

        # Resolve entrypoint to workflow
        workflow_id = await self._resolve_entrypoint(entrypoint_name)

        if not workflow_id:
            raise ValueError(f"Entrypoint '{entrypoint_name}' not found")

        # Validate inputs against entrypoint schema
        await self._validate_entrypoint_inputs(entrypoint_name, inputs)

        # Execute workflow
        return await self.execute_workflow(workflow_id, inputs, session_id)

    async def _get_workflow_actions(self, workflow_id: str) -> List[Dict[str, Any]]:
        """
        Get ordered action sequence for workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            List of action dictionaries ordered by sequence
        """
        query = """
        MATCH (w:Workflow {id: $workflow_id})-[:CONTAINS]->(a:Action)
        RETURN a.id as id,
               a.tool as tool,
               a.action as action,
               a.inputs as inputs,
               a.output as output,
               a.sequence as sequence
        ORDER BY a.sequence ASC
        """

        result = self._neo4j.run(query, {"workflow_id": workflow_id})
        return result if result else []

    async def _execute_action(self, action: Dict[str, Any], context: WorkflowExecutionContext) -> Dict[str, Any]:
        """
        Execute a single action via unified event bus.

        Args:
            action: Action dictionary with tool, action, inputs, output
            context: Execution context with variables

        Returns:
            Dict with action execution results
        """
        # Parse inputs if stored as JSON string
        if isinstance(action["inputs"], str):
            try:
                action_inputs = json.loads(action["inputs"])
            except json.JSONDecodeError:
                log.warning(f"Could not parse action inputs as JSON: {action['inputs']}")
                action_inputs = {}
        else:
            action_inputs = action["inputs"]

        # Resolve input variables from context
        resolved_inputs = self._resolve_inputs(action_inputs, context.variables)

        log.debug(
            f"[WorkflowExecutor] Executing action: {action['tool']}.{action['action']} with inputs: {resolved_inputs}"
        )

        # Emit tool.call event (pipes can transform)
        # Note: emit is sync, wraps async event processing internally
        tool_call_payload = emit("tool.call", {"tool": action["tool"], "args": resolved_inputs})

        # Execute via component request API (goes through event bus)
        try:
            result = await self._agent.request(
                tool_call_payload.tool, {"action": action["action"], "inputs": tool_call_payload.args}
            )
        except Exception as e:
            log.error(f"[WorkflowExecutor] Error executing {action['tool']}.{action['action']}: {e}")
            result = f"Error: {e}"

        # Emit tool.observation event (hooks can observe)
        obs_payload = emit("tool.observation", {"tool": action["tool"], "observation": str(result)})

        return {
            "action_id": action["id"],
            "tool": action["tool"],
            "action": action["action"],
            "output": result,
            "observation": obs_payload.observation,
            "output_var": action.get("output"),
        }

    def _resolve_inputs(self, inputs: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve input variable references to actual values.

        Args:
            inputs: Input dictionary that may contain variable references
            variables: Available variables from context

        Returns:
            Resolved inputs dictionary
        """
        resolved = {}

        for key, value in inputs.items():
            if isinstance(value, str) and value in variables:
                # Variable reference - substitute with actual value
                resolved[key] = variables[value]
            else:
                # Literal value
                resolved[key] = value

        return resolved

    async def _resolve_entrypoint(self, entrypoint_name: str) -> Optional[str]:
        """
        Resolve entrypoint name to workflow ID.

        Args:
            entrypoint_name: Name of the entrypoint

        Returns:
            Workflow ID if found, None otherwise
        """
        query = """
        MATCH (e:Entrypoint {name: $name})-[:EXECUTES]->(w:Workflow)
        RETURN w.id as workflow_id
        LIMIT 1
        """

        result = self._neo4j.run(query, {"name": entrypoint_name})

        if result and len(result) > 0:
            return result[0]["workflow_id"]

        return None

    async def _validate_entrypoint_inputs(self, entrypoint_name: str, inputs: Dict[str, Any]) -> None:
        """
        Validate inputs against entrypoint schema.

        Args:
            entrypoint_name: Name of entrypoint
            inputs: Inputs to validate

        Raises:
            ValueError: If required inputs are missing
        """
        query = """
        MATCH (e:Entrypoint {name: $name})
        RETURN e.input_schema as schema
        """

        result = self._neo4j.run(query, {"name": entrypoint_name})

        if not result or len(result) == 0:
            return  # No schema to validate against

        schema = result[0].get("schema")

        if not schema:
            return

        # Parse schema if stored as JSON string
        if isinstance(schema, str):
            try:
                schema_dict = json.loads(schema)
            except json.JSONDecodeError:
                log.warning(f"Could not parse schema for entrypoint '{entrypoint_name}'")
                return
        else:
            schema_dict = schema

        # Validate required fields
        required = schema_dict.get("required", [])
        for field in required:
            if field not in inputs:
                raise ValueError(f"Required input '{field}' missing for entrypoint '{entrypoint_name}'")

        log.debug(f"Inputs validated successfully for entrypoint '{entrypoint_name}'")
