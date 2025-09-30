"""Workflows Feature Implementation with Auto-Component Creation.

This module provides automatic workflow caching and retrieval functionality with auto-created Neo4j components.
When enabled, it creates intelligent workflow management that learns from previous executions.
"""

import logging
import json
from typing import Dict, List, Tuple, Callable, Any
from dataclasses import replace
from woodwork.types.events import AgentActionPayload, AgentStepCompletePayload, InputReceivedPayload
from woodwork.types.workflows import Action
from .base import InternalFeature

log = logging.getLogger(__name__)


class WorkflowsFeature(InternalFeature):
    """Internal feature for automatic workflow management with auto-created Neo4j component."""

    def __init__(self):
        self._neo4j_component = None
        self._component_ref = None
        self._current_workflow_id = None
        self._workflow_actions = []
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

        # Attach to component for access
        component._workflows_db = self._neo4j_component
        component._workflows_mode = True
        log.info(f"Workflows feature setup complete for component: {component.name}")

    def _initialize_graph_schema(self):
        """Set up the graph schema for workflows."""
        try:
            # Create constraints and indices for better performance
            schema_queries = [
                "CREATE CONSTRAINT prompt_id IF NOT EXISTS FOR (p:Prompt) REQUIRE p.id IS UNIQUE",
                "CREATE CONSTRAINT action_id IF NOT EXISTS FOR (a:Action) REQUIRE a.id IS UNIQUE",
                "CREATE CONSTRAINT workflow_id IF NOT EXISTS FOR (w:Workflow) REQUIRE w.id IS UNIQUE",
                "CREATE INDEX prompt_text IF NOT EXISTS FOR (p:Prompt) ON (p.text)",
                "CREATE INDEX action_tool IF NOT EXISTS FOR (a:Action) ON (a.tool)",
                "CREATE INDEX workflow_status IF NOT EXISTS FOR (w:Workflow) ON (w.status)"
            ]

            for query in schema_queries:
                try:
                    self._neo4j_component.run(query)
                except Exception as e:
                    # Constraint/index might already exist
                    log.debug(f"Schema setup query failed (likely already exists): {e}")

            log.debug("Graph schema initialized")
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
            ("agent.step_complete", self._complete_workflow_hook)
        ]

    def get_pipes(self) -> List[Tuple[str, Callable]]:
        """Return workflow-related pipes."""
        return [
            ("input.received", self._check_similar_workflows_pipe)
        ]

    def _extract_api_key(self, component) -> str:
        """Extract API key from component's model."""
        if hasattr(component, 'model') and hasattr(component.model, '_api_key'):
            return component.model._api_key
        return None

    def _check_similar_workflows_pipe(self, payload: InputReceivedPayload) -> InputReceivedPayload:
        """Check for similar workflows and inject context if found."""
        if not self._neo4j_component:
            return payload

        try:
            log.debug(f"Checking for similar workflows for input: {payload.input[:50]}...")

            # Search for similar prompts
            similar_prompts = self._neo4j_component.similarity_search(
                payload.input, "Prompt", "text"
            )

            if similar_prompts and len(similar_prompts) > 0:
                best_match = similar_prompts[0]
                similarity_score = best_match.get("score", 0)

                if similarity_score > 0.85:  # High similarity threshold
                    log.debug(f"Found similar workflow with score: {similarity_score}")

                    # Get the workflow chain for context
                    workflow_context = self._get_workflow_context(best_match.get("nodeID"))

                    if workflow_context:
                        # Inject workflow context into input
                        enhanced_input = f"{payload.input}\n\n[Similar Workflow Context]:\n{workflow_context}"
                        return replace(payload, input=enhanced_input)

        except Exception as e:
            # Context lookup failed, continue without enhancement
            log.debug(f"Workflow context lookup failed: {e}")

        # Start new workflow tracking
        self._start_new_workflow(payload.input)
        return payload

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
            WITH a
            CALL db.create.setNodeVectorProperty(a, 'embedding',
                genai.vector.encode($action_text, "OpenAI", {token: $api_key}))
            RETURN a.id as action_id
            """

            action_text = f"{tool} {action_name} {json.dumps(inputs)}"

            result = self._neo4j_component.run(query, {
                "workflow_id": self._current_workflow_id,
                "action_id": action_id,
                "tool": tool,
                "action_name": action_name,
                "inputs_json": json.dumps(inputs),
                "output_var": output_var,
                "sequence": len(self._workflow_actions),
                "action_text": action_text,
                "api_key": self._extract_api_key(self._component_ref)
            })

            # Create relationships
            self._create_action_relationships(action_id, inputs, output_var)

            # Track for dependency resolution
            self._workflow_actions.append({
                "id": action_id,
                "tool": tool,
                "action": action_name,
                "inputs": inputs,
                "output": output_var
            })

            log.debug(f"Action synced to workflow: {action_id}")

        except Exception as e:
            log.warning(f"Failed to sync action: {e}")

    def _create_action_relationships(self, action_id: str, inputs: Dict[str, Any], output_var: str):
        """Create proper relationships for the action based on dependencies."""
        try:
            # Find input dependencies (variables that match previous action outputs)
            dependencies = []
            for input_value in inputs.values():
                if isinstance(input_value, str):
                    # Check if this input matches any previous action's output
                    for prev_action in self._workflow_actions:
                        if prev_action["output"] == input_value:
                            dependencies.append(prev_action["id"])

            if dependencies:
                # Create DEPENDS_ON relationships
                for dep_id in dependencies:
                    dep_query = """
                    MATCH (current:Action {id: $action_id})
                    MATCH (dep:Action {id: $dep_id})
                    CREATE (current)-[:DEPENDS_ON]->(dep)
                    """
                    self._neo4j_component.run(dep_query, {
                        "action_id": action_id,
                        "dep_id": dep_id
                    })

                # Create NEXT relationship from last dependency
                if len(self._workflow_actions) > 0:
                    prev_action_id = self._workflow_actions[-1]["id"]
                    next_query = """
                    MATCH (prev:Action {id: $prev_id})
                    MATCH (current:Action {id: $action_id})
                    CREATE (prev)-[:NEXT]->(current)
                    """
                    self._neo4j_component.run(next_query, {
                        "prev_id": prev_action_id,
                        "action_id": action_id
                    })
            else:
                # No dependencies - link to prompt (first action)
                if len(self._workflow_actions) == 0:
                    start_query = """
                    MATCH (p:Prompt {workflow_id: $workflow_id})
                    MATCH (a:Action {id: $action_id})
                    CREATE (p)-[:STARTS]->(a)
                    """
                    self._neo4j_component.run(start_query, {
                        "workflow_id": self._current_workflow_id,
                        "action_id": action_id
                    })
                else:
                    # Sequential action - link to previous
                    prev_action_id = self._workflow_actions[-1]["id"]
                    next_query = """
                    MATCH (prev:Action {id: $prev_id})
                    MATCH (current:Action {id: $action_id})
                    CREATE (prev)-[:NEXT]->(current)
                    """
                    self._neo4j_component.run(next_query, {
                        "prev_id": prev_action_id,
                        "action_id": action_id
                    })

        except Exception as e:
            log.warning(f"Failed to create action relationships: {e}")

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

# Register when module is imported
_register_feature()