"""Unified Workflows Feature Implementation with Auto-Component Creation.

This module provides automatic workflow caching and retrieval functionality with auto-created Neo4j components.
When enabled, it creates intelligent workflow management that learns from previous executions.

Features:
- Auto-capture workflows during agent execution
- Similarity-based workflow retrieval (top 3 matches)
- Workflows exposed as tools for agents
- Direct workflow execution via entrypoints
- Manual workflow creation/editing support
"""

import logging
import json
from typing import Dict, List, Tuple, Callable, Any, Optional
from dataclasses import replace
from woodwork.types.events import AgentActionPayload, AgentStepCompletePayload, InputReceivedPayload
from woodwork.types.workflows import Action
from .base import InternalFeature
from .workflow_executor import WorkflowExecutor

log = logging.getLogger(__name__)


class WorkflowsFeature(InternalFeature):
    """Internal feature for automatic workflow management with auto-created Neo4j component."""

    def __init__(self):
        self._neo4j_component = None
        self._component_ref = None
        self._current_workflow_id = None
        self._workflow_actions = []
        self._workflow_executor = None  # Workflow executor for direct execution
        log.debug("WorkflowsFeature initialized")

    def get_required_components(self) -> List[Dict[str, Any]]:
        """Define required Neo4j component for workflow management."""
        return [
            {
                "component_type": "neo4j",
                "component_id": "workflows_neo4j",
                "config": {
                    "uri": "bolt://localhost:7687",
                    "user": "neo4j",
                    "password": "testpassword",
                    "name": "workflows_db"
                },
                "optional": False
            }
        ]

    def _setup_feature(self, component: 'component', config: Dict, component_manager) -> None:
        """Initialize workflows with auto-created Neo4j component."""
        log.debug(f"Setting up WorkflowsFeature for component: {component.name}")
        self._component_ref = component

        # Get API key from model (existing pattern)
        api_key = self._extract_api_key(component)
        if not api_key:
            raise TypeError("Workflows feature requires API key from model configuration.")

        # Get or create Neo4j component through component manager
        neo4j_config = {
            "uri": config.get("workflows_uri", "bolt://localhost:7687"),
            "user": config.get("workflows_user", "neo4j"),
            "password": config.get("workflows_password", "testpassword"),
            "name": f"{component.name}_workflows",
            "api_key": api_key
        }

        log.debug(f"Creating Neo4j component with config: {neo4j_config}")
        self._neo4j_component = component_manager.get_or_create_component(
            component_id=f"{component.name}_workflows_neo4j",
            component_type="neo4j",
            config=neo4j_config
        )

        # Initialize vector indices for similarity search
        try:
            # Index for prompts
            self._neo4j_component.init_vector_index(
                index_name="prompt_embeddings",
                label="Prompt",
                property="embedding"
            )
            # Index for actions
            self._neo4j_component.init_vector_index(
                index_name="action_embeddings",
                label="Action",
                property="embedding"
            )
            log.debug("Vector indices initialized successfully")
        except Exception as e:
            # Indices might already exist, which is fine
            log.debug(f"Vector index initialization: {e}")

        # Initialize graph schema
        self._initialize_graph_schema()

        # Create workflow executor for direct execution
        # Note: task_master is deprecated, so we make this optional
        # Workflow CAPTURE still works without executor (executor is only for execute_workflow tool)
        task_master = getattr(component, 'task_m', None)
        if task_master:
            self._workflow_executor = WorkflowExecutor(self._neo4j_component, task_master)
            log.debug("Workflow executor created with task_master")
        else:
            log.debug("No task_master available - workflow capture enabled, execute_workflow tool will not be available")

        # Attach to component for access
        component._workflows_db = self._neo4j_component
        component._workflows_mode = True
        component._workflow_executor = self._workflow_executor  # For access from API inputs
        log.info(f"Workflows feature setup complete for component: {component.name}")

    def _initialize_graph_schema(self):
        """Set up the graph schema for workflows including entrypoints."""
        try:
            # Create constraints and indices for better performance
            schema_queries = [
                "CREATE CONSTRAINT prompt_id IF NOT EXISTS FOR (p:Prompt) REQUIRE p.id IS UNIQUE",
                "CREATE CONSTRAINT action_id IF NOT EXISTS FOR (a:Action) REQUIRE a.id IS UNIQUE",
                "CREATE CONSTRAINT workflow_id IF NOT EXISTS FOR (w:Workflow) REQUIRE w.id IS UNIQUE",
                "CREATE CONSTRAINT entrypoint_name IF NOT EXISTS FOR (e:Entrypoint) REQUIRE e.name IS UNIQUE",
                "CREATE INDEX prompt_text IF NOT EXISTS FOR (p:Prompt) ON (p.text)",
                "CREATE INDEX action_tool IF NOT EXISTS FOR (a:Action) ON (a.tool)",
                "CREATE INDEX workflow_status IF NOT EXISTS FOR (w:Workflow) ON (w.status)",
                "CREATE INDEX workflow_source IF NOT EXISTS FOR (w:Workflow) ON (w.source)",
                "CREATE INDEX entrypoint_name_idx IF NOT EXISTS FOR (e:Entrypoint) ON (e.name)"
            ]

            for query in schema_queries:
                try:
                    self._neo4j_component.run(query)
                except Exception as e:
                    # Constraint/index might already exist
                    log.debug(f"Schema setup query failed (likely already exists): {e}")

            log.debug("Graph schema initialized with entrypoint support")
        except Exception as e:
            log.warning(f"Failed to initialize graph schema: {e}")

    def teardown(self, component: 'component', component_manager) -> None:
        """Clean up workflows (component manager handles Neo4j cleanup)."""
        log.debug(f"Tearing down WorkflowsFeature for component: {component.name}")

        # Remove references from component
        if hasattr(component, '_workflows_db'):
            delattr(component, '_workflows_db')
        if hasattr(component, '_workflows_mode'):
            delattr(component, '_workflows_mode')

        # Component manager will handle actual Neo4j component cleanup
        self._neo4j_component = None
        self._current_workflow_id = None
        self._workflow_actions = []
        log.debug(f"WorkflowsFeature teardown complete for component: {component.name}")

    def get_hooks(self) -> List[Tuple[str, Callable]]:
        """Return workflow-related hooks."""
        return [
            ("agent.action", self._sync_action_hook),
            # NOTE: Removed agent.step_complete hook because it fires after EVERY action,
            # not just when agent is done. Workflows will stay "in_progress" until
            # explicitly completed or timeout. This is correct since we want to capture
            # all actions, not close the workflow after the first one.
            # ("agent.step_complete", self._complete_workflow_hook)
        ]

    def get_pipes(self) -> List[Tuple[str, Callable]]:
        """Return workflow-related pipes."""
        return [
            ("input.received", self._check_similar_workflows_pipe)
        ]

    def get_tools(self) -> List[Dict[str, Any]]:
        """Return workflow execution tools for the agent."""
        if not self._workflow_executor:
            return []

        return [
            {
                "name": "execute_workflow",
                "description": "Execute a saved workflow by ID with given inputs. Use this when you find a similar workflow that matches the current task.",
                "parameters": {
                    "workflow_id": {
                        "type": "string",
                        "description": "ID of the workflow to execute"
                    },
                    "inputs": {
                        "type": "object",
                        "description": "Input variables for the workflow"
                    }
                },
                "function": self._execute_workflow_tool
            }
        ]

    async def _execute_workflow_tool(self, workflow_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Tool function for agent to execute workflows."""
        if not self._workflow_executor:
            raise ValueError("Workflow executor not initialized")

        # Get current session ID from component ref
        session_id = getattr(self._component_ref, 'session_id', 'default')

        log.info(f"Agent executing workflow {workflow_id} with inputs: {inputs}")

        return await self._workflow_executor.execute_workflow(
            workflow_id, inputs, session_id
        )

    def _extract_api_key(self, component) -> str:
        """Extract API key from component's model."""
        if hasattr(component, 'model') and hasattr(component.model, '_api_key'):
            return component.model._api_key
        return None

    def _check_similar_workflows_pipe(self, payload: InputReceivedPayload) -> InputReceivedPayload:
        """Check for similar workflows and inject top 3 as context and tools."""
        if not self._neo4j_component:
            return payload

        # Check if we already have a workflow started (pipe might be called multiple times)
        if self._current_workflow_id:
            log.debug(f"Workflow already started: {self._current_workflow_id}, skipping pipe")
            return payload

        try:
            log.debug(f"Checking for similar workflows for input: {payload.input[:50]}...")

            # Search for top 3 similar prompts
            similar_prompts = self._neo4j_component.similarity_search(
                payload.input, "Prompt", "text", limit=3
            )

            if similar_prompts and len(similar_prompts) > 0:
                # Build workflow context with actual action sequences
                workflow_contexts = []

                for i, match in enumerate(similar_prompts, 1):
                    similarity_score = match.get("score", 0)

                    if similarity_score > 0.75:  # Relevance threshold
                        workflow_data = self._get_workflow_detail(match.get("nodeID"))

                        if workflow_data:
                            workflow_contexts.append({
                                'rank': i,
                                'similarity': similarity_score,
                                'workflow_id': workflow_data.get('workflow_id'),
                                'name': workflow_data.get('name', f'Workflow {i}'),
                                'description': workflow_data.get('description', ''),
                                'actions': workflow_data.get('actions', [])
                            })

                if workflow_contexts:
                    log.info(f"Found {len(workflow_contexts)} similar workflows, injecting as context")

                    # Format and inject workflow contexts
                    context_text = self._format_workflow_contexts(workflow_contexts)

                    enhanced_input = f"""{payload.input}

[Available Similar Workflows]:
{context_text}

You can either:
1. Use execute_workflow(workflow_id, inputs) to run an exact workflow
2. Use the workflow structure as guidance for your own solution
"""

                    # Start new workflow tracking (even when reusing, we track the new execution)
                    self._start_new_workflow(payload.input)
                    return replace(payload, input=enhanced_input)

        except Exception as e:
            # Context lookup failed, continue without enhancement
            log.debug(f"Workflow context lookup failed: {e}")

        # Start new workflow tracking
        self._start_new_workflow(payload.input)
        return payload

    def _format_workflow_contexts(self, contexts: List[Dict]) -> str:
        """Format workflow contexts for agent consumption."""
        lines = []

        for ctx in contexts:
            lines.append(
                f"\n{ctx['rank']}. {ctx['name']} "
                f"(ID: {ctx['workflow_id']}, Similarity: {ctx['similarity']:.0%})"
            )

            if ctx.get('description'):
                lines.append(f"   Description: {ctx['description']}")

            lines.append("   Steps:")
            for j, action in enumerate(ctx['actions'][:5], 1):  # Limit to 5 steps
                inputs_str = json.dumps(action.get('inputs', {}))
                lines.append(
                    f"      {j}. {action['tool']}.{action['action']}({inputs_str}) "
                    f"→ {action['output']}"
                )

            if len(ctx['actions']) > 5:
                lines.append(f"      ... and {len(ctx['actions']) - 5} more steps")

        return '\n'.join(lines)

    def _get_workflow_detail(self, prompt_node_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed workflow information from a prompt node."""
        try:
            # Query to get workflow and action chain
            query = """
            MATCH (p:Prompt)
            WHERE elementId(p) = $prompt_id
            MATCH (p)<-[:CONTAINS]-(w:Workflow)
            OPTIONAL MATCH (p)-[:STARTS]->(first:Action)
            OPTIONAL MATCH path = (first)-[:NEXT*0..20]->(a:Action)
            WITH w, p, collect(DISTINCT first) + collect(DISTINCT a) as all_actions
            UNWIND all_actions as action
            WITH w, p, action
            WHERE action IS NOT NULL
            RETURN w.id as workflow_id,
                   w.name as name,
                   w.description as description,
                   p.text as prompt,
                   collect({
                       tool: action.tool,
                       action: action.action,
                       inputs: action.inputs,
                       output: action.output,
                       sequence: action.sequence
                   }) as actions
            """

            result = self._neo4j_component.run(query, {"prompt_id": prompt_node_id})

            if result and len(result) > 0:
                workflow = result[0]

                # Sort actions by sequence
                actions = sorted(
                    workflow.get("actions", []),
                    key=lambda x: x.get('sequence', 0)
                )

                # Parse inputs if stored as JSON strings
                for action in actions:
                    if isinstance(action.get('inputs'), str):
                        try:
                            action['inputs'] = json.loads(action['inputs'])
                        except json.JSONDecodeError:
                            action['inputs'] = {}

                return {
                    'workflow_id': workflow.get('workflow_id'),
                    'name': workflow.get('name'),
                    'description': workflow.get('description'),
                    'prompt': workflow.get('prompt'),
                    'actions': actions
                }

        except Exception as e:
            log.debug(f"Failed to get workflow detail: {e}")

        return None

    def _get_workflow_context(self, prompt_node_id: str) -> str:
        """Get workflow context from a prompt node."""
        try:
            # Query to get the action chain from this prompt
            query = """
            MATCH (p:Prompt)
            WHERE elementId(p) = $prompt_id
            MATCH (p)-[:STARTS]->(first:Action)
            OPTIONAL MATCH path = (first)-[:NEXT*0..10]->(a:Action)
            WITH p, collect(DISTINCT a) as actions
            RETURN p.text as prompt,
                   [action IN actions | {tool: action.tool, action: action.action, output: action.output}] as workflow
            LIMIT 1
            """

            result = self._neo4j_component.run(query, {"prompt_id": prompt_node_id})

            if result and len(result) > 0:
                workflow_data = result[0]
                actions = workflow_data.get("workflow", [])

                # Format as readable context
                context_lines = []
                for i, action in enumerate(actions[:5], 1):  # Limit to first 5 actions
                    context_lines.append(f"  {i}. Use {action['tool']} to {action['action']}")

                return "\n".join(context_lines)

        except Exception as e:
            log.debug(f"Failed to get workflow context: {e}")

        return ""

    def _start_new_workflow(self, input_text: str):
        """Start tracking a new workflow."""
        import uuid
        self._current_workflow_id = str(uuid.uuid4())
        self._workflow_actions = []

        try:
            # Create workflow and prompt nodes
            query = """
            CREATE (w:Workflow {
                id: $workflow_id,
                status: 'in_progress',
                source: 'auto',
                created_at: datetime(),
                component_id: $component_id
            })
            CREATE (p:Prompt {
                id: $prompt_id,
                text: $input_text,
                workflow_id: $workflow_id
            })
            CREATE (w)-[:CONTAINS]->(p)
            WITH p
            CALL db.create.setNodeVectorProperty(p, 'embedding',
                genai.vector.encode($input_text, "OpenAI", {token: $api_key}))
            RETURN p.id as prompt_id
            """

            result = self._neo4j_component.run(query, {
                "workflow_id": self._current_workflow_id,
                "prompt_id": f"prompt_{self._current_workflow_id}",
                "input_text": input_text,
                "component_id": self._component_ref.name if self._component_ref else "unknown",
                "api_key": self._extract_api_key(self._component_ref)
            })

            log.debug(f"Started new workflow: {self._current_workflow_id}")

        except Exception as e:
            log.warning(f"Failed to create workflow nodes: {e}")

    def _sync_action_hook(self, payload: AgentActionPayload) -> None:
        """Sync action incrementally to the graph database."""
        if not self._neo4j_component or not self._current_workflow_id:
            return

        try:
            log.debug(f"Syncing action to workflow: {payload.action}")

            # Parse action if it's a string
            if isinstance(payload.action, str):
                try:
                    action_data = json.loads(payload.action)
                except json.JSONDecodeError:
                    log.warning(f"Could not parse action as JSON: {payload.action}")
                    return
            else:
                action_data = payload.action

            # Extract action details
            tool = action_data.get("tool", "unknown")
            action_name = action_data.get("action", "unknown")
            inputs = action_data.get("inputs", {})
            output_var = action_data.get("output", "unknown")

            action_id = f"action_{self._current_workflow_id}_{len(self._workflow_actions)}"

            # Create action node
            # Note: Vector embedding is done in separate query to avoid failing if OpenAI is unavailable
            query = """
            MATCH (w:Workflow {id: $workflow_id})
            CREATE (a:Action {
                id: $action_id,
                tool: $tool,
                action: $action_name,
                inputs: $inputs_json,
                output: $output_var,
                sequence: $sequence,
                workflow_id: $workflow_id,
                created_at: datetime()
            })
            CREATE (w)-[:CONTAINS]->(a)
            RETURN a.id as action_id
            """

            action_text = f"{tool} {action_name} {json.dumps(inputs)}"

            # IMPORTANT: Track action BEFORE creating relationships
            # This ensures the first action gets properly linked to the prompt
            current_action = {
                "id": action_id,
                "tool": tool,
                "action": action_name,
                "inputs": inputs,
                "output": output_var,
                "sequence": len(self._workflow_actions)
            }

            result = self._neo4j_component.run(query, {
                "workflow_id": self._current_workflow_id,
                "action_id": action_id,
                "tool": tool,
                "action_name": action_name,
                "inputs_json": json.dumps(inputs),
                "output_var": output_var,
                "sequence": current_action["sequence"]
            })

            # Add vector embedding (non-blocking - failure won't prevent action creation)
            try:
                embedding_query = """
                MATCH (a:Action {id: $action_id})
                CALL db.create.setNodeVectorProperty(a, 'embedding',
                    genai.vector.encode($action_text, "OpenAI", {token: $api_key}))
                RETURN a.id
                """
                self._neo4j_component.run(embedding_query, {
                    "action_id": action_id,
                    "action_text": action_text,
                    "api_key": self._extract_api_key(self._component_ref)
                })
                log.debug(f"Vector embedding added for action: {action_id}")
            except Exception as embed_error:
                log.warning(f"Failed to add vector embedding for action {action_id}: {embed_error}")

            # Add to tracking list BEFORE creating relationships
            self._workflow_actions.append(current_action)

            # Now create relationships (this needs the action in the list)
            self._create_action_relationships(action_id, inputs, output_var)

            log.info(f"Action synced to workflow: {action_id} (sequence: {current_action['sequence']}, tool: {tool}.{action_name})")

        except Exception as e:
            log.error(f"Failed to sync action to workflow {self._current_workflow_id}: {e}", exc_info=True)

    def _create_action_relationships(self, action_id: str, inputs: Dict[str, Any], output_var: str):
        """Create proper relationships for the action based on dependencies."""
        try:
            # Get the current action's sequence (it's already in the list)
            current_sequence = None
            for action in self._workflow_actions:
                if action["id"] == action_id:
                    current_sequence = action["sequence"]
                    break

            if current_sequence is None:
                log.warning(f"Could not find sequence for action {action_id}")
                return

            # Find input dependencies (variables that match previous action outputs)
            dependencies = []
            for input_value in inputs.values():
                if isinstance(input_value, str):
                    # Check if this input matches any previous action's output
                    for prev_action in self._workflow_actions:
                        if prev_action["id"] != action_id and prev_action["output"] == input_value:
                            dependencies.append(prev_action["id"])
                            log.debug(f"Action {action_id} depends on {prev_action['id']} (output: {input_value})")

            # First action: Link to prompt with STARTS
            if current_sequence == 0:
                start_query = """
                MATCH (p:Prompt {workflow_id: $workflow_id})
                MATCH (a:Action {id: $action_id})
                CREATE (p)-[:STARTS]->(a)
                """
                self._neo4j_component.run(start_query, {
                    "workflow_id": self._current_workflow_id,
                    "action_id": action_id
                })
                log.debug(f"Created STARTS relationship: Prompt -> {action_id}")

            # Create DEPENDS_ON relationships for variable dependencies
            if dependencies:
                for dep_id in dependencies:
                    dep_query = """
                    MATCH (current:Action {id: $action_id})
                    MATCH (dep:Action {id: $dep_id})
                    MERGE (current)-[:DEPENDS_ON]->(dep)
                    """
                    self._neo4j_component.run(dep_query, {
                        "action_id": action_id,
                        "dep_id": dep_id
                    })
                    log.debug(f"Created DEPENDS_ON relationship: {action_id} -> {dep_id}")

            # Create NEXT relationship from previous action (sequential flow)
            if current_sequence > 0:
                # Find the previous action by sequence
                prev_action = None
                for action in self._workflow_actions:
                    if action["sequence"] == current_sequence - 1:
                        prev_action = action
                        break

                if prev_action:
                    next_query = """
                    MATCH (prev:Action {id: $prev_id})
                    MATCH (current:Action {id: $action_id})
                    MERGE (prev)-[:NEXT]->(current)
                    """
                    self._neo4j_component.run(next_query, {
                        "prev_id": prev_action["id"],
                        "action_id": action_id
                    })
                    log.debug(f"Created NEXT relationship: {prev_action['id']} -> {action_id}")

        except Exception as e:
            log.error(f"Failed to create action relationships for {action_id}: {e}", exc_info=True)

    def _complete_workflow_hook(self, payload: AgentStepCompletePayload) -> None:
        """Mark workflow as complete when agent finishes."""
        if not self._neo4j_component or not self._current_workflow_id:
            return

        try:
            log.debug(f"Completing workflow: {self._current_workflow_id}")

            # Update workflow status
            query = """
            MATCH (w:Workflow {id: $workflow_id})
            SET w.status = 'completed',
                w.completed_at = datetime(),
                w.final_step = $step,
                w.session_id = $session_id
            RETURN w.id as workflow_id
            """

            self._neo4j_component.run(query, {
                "workflow_id": self._current_workflow_id,
                "step": payload.step,
                "session_id": payload.session_id
            })

            log.info(f"Workflow completed: {self._current_workflow_id}")

            # Reset for next workflow
            self._current_workflow_id = None
            self._workflow_actions = []

        except Exception as e:
            log.warning(f"Failed to complete workflow: {e}")


# Register the feature (import at module level to avoid circular imports)
def _register_feature():
    from .base import InternalFeatureRegistry
    InternalFeatureRegistry.register("workflows", WorkflowsFeature)
    # Register as graph_cache for backward compatibility
    InternalFeatureRegistry.register("graph_cache", WorkflowsFeature)

# Register when module is imported
_register_feature()