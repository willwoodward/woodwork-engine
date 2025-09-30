"""Knowledge Graph Feature Implementation with Auto-Component Creation.

This demonstrates how to add a new agent property that automatically creates
Neo4j components with custom hooks and pipes.

Usage in .ww config:
    my_agent = agent llm {
        knowledge_graph: true  # ← This single line creates everything!
        model: my_llm
        tools: [...]
    }
"""

import logging
from typing import Dict, List, Tuple, Callable, Any
from woodwork.types.events import AgentThoughtPayload, AgentActionPayload, AgentStepCompletePayload, InputReceivedPayload
from .base import InternalFeature

log = logging.getLogger(__name__)


class KnowledgeGraphFeature(InternalFeature):
    """
    Internal feature that creates a Neo4j knowledge graph with intelligent hooks and pipes.

    This feature demonstrates the power of the internal features system:
    - Automatically creates Neo4j component
    - Registers hooks to capture agent thoughts and store as knowledge
    - Registers pipes to enhance input with relevant graph knowledge
    - All from a single `knowledge_graph: true` in config!
    """

    def __init__(self):
        self._neo4j_component = None
        self._component_ref = None
        log.debug("KnowledgeGraphFeature initialized")

    def get_required_components(self) -> List[Dict[str, Any]]:
        """Define required Neo4j component for knowledge graph."""
        return [
            {
                "component_type": "neo4j",
                "component_id": "knowledge_graph_neo4j",
                "config": {
                    "uri": "bolt://localhost:7687",
                    "user": "neo4j",
                    "password": "testpassword",
                    "name": "knowledge_graph_db"
                },
                "optional": False
            }
        ]

    def _setup_feature(self, component: 'component', config: Dict, component_manager) -> None:
        """Initialize knowledge graph with auto-created Neo4j component."""
        log.debug(f"Setting up KnowledgeGraphFeature for component: {component.name}")
        self._component_ref = component

        # Get API key from model (for embeddings)
        api_key = self._extract_api_key(component)
        if not api_key:
            raise TypeError("Knowledge graph requires API key from model configuration.")

        # Get or create Neo4j component through component manager
        neo4j_config = {
            "uri": config.get("knowledge_graph_uri", "bolt://localhost:7687"),
            "user": config.get("knowledge_graph_user", "neo4j"),
            "password": config.get("knowledge_graph_password", "testpassword"),
            "name": f"{component.name}_knowledge_graph",
            "api_key": api_key
        }

        log.debug(f"Creating Neo4j component with config: {neo4j_config}")
        self._neo4j_component = component_manager.get_or_create_component(
            component_id=f"{component.name}_knowledge_graph_neo4j",
            component_type="neo4j",
            config=neo4j_config
        )

        # Initialize knowledge graph schema
        try:
            self._initialize_knowledge_schema()
            log.debug("Knowledge graph schema initialized successfully")
        except Exception as e:
            log.debug(f"Knowledge graph schema initialization: {e}")

        # Attach to component for access
        component._knowledge_graph = self._neo4j_component
        component._knowledge_mode = True
        log.info(f"Knowledge graph feature setup complete for component: {component.name}")

    def _initialize_knowledge_schema(self):
        """Initialize the knowledge graph schema with nodes and relationships."""
        # Create constraints and indexes for optimal performance
        schema_queries = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Concept) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Thought) REQUIRE t.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (a:Action) REQUIRE a.id IS UNIQUE",
            "CREATE INDEX IF NOT EXISTS FOR (c:Concept) ON (c.embedding)",
            "CREATE INDEX IF NOT EXISTS FOR (t:Thought) ON (t.timestamp)"
        ]

        for query in schema_queries:
            try:
                self._neo4j_component.run_query(query)
            except Exception as e:
                log.debug(f"Schema query failed (may already exist): {e}")

    def teardown(self, component: 'component', component_manager) -> None:
        """Clean up knowledge graph (component manager handles Neo4j cleanup)."""
        log.debug(f"Tearing down KnowledgeGraphFeature for component: {component.name}")

        # Remove references from component
        if hasattr(component, '_knowledge_graph'):
            delattr(component, '_knowledge_graph')
        if hasattr(component, '_knowledge_mode'):
            delattr(component, '_knowledge_mode')

        # Component manager will handle actual Neo4j component cleanup
        self._neo4j_component = None
        log.debug(f"KnowledgeGraphFeature teardown complete for component: {component.name}")

    def get_hooks(self) -> List[Tuple[str, Callable]]:
        """Return knowledge graph hooks."""
        return [
            ("agent.thought", self._capture_thought_hook),
            ("agent.action", self._capture_action_hook),
            ("agent.step_complete", self._update_knowledge_hook)
        ]

    def get_pipes(self) -> List[Tuple[str, Callable]]:
        """Return knowledge graph pipes."""
        return [
            ("input.received", self._enhance_with_knowledge_pipe)
        ]

    def _extract_api_key(self, component) -> str:
        """Extract API key from component's model."""
        if hasattr(component, 'model') and hasattr(component.model, '_api_key'):
            return component.model._api_key
        return None

    def _enhance_with_knowledge_pipe(self, payload: InputReceivedPayload) -> InputReceivedPayload:
        """Enhance input with relevant knowledge from the graph."""
        if not self._neo4j_component:
            return payload

        try:
            log.debug(f"Enhancing input with knowledge graph: {payload.input[:50]}...")

            # Search for relevant concepts in the knowledge graph
            relevant_concepts = self._neo4j_component.similarity_search(
                payload.input, "Concept", "description"
            )

            if relevant_concepts:
                # Extract the most relevant knowledge
                knowledge_context = []
                for concept in relevant_concepts[:3]:  # Top 3 most relevant
                    if concept.get("score", 0) > 0.7:  # High relevance threshold
                        knowledge_context.append(f"- {concept.get('description', '')}")

                if knowledge_context:
                    enhanced_input = f"{payload.input}\n\nRelevant Knowledge:\n" + "\n".join(knowledge_context)

                    # Create new payload with enhanced input
                    enhanced_payload = InputReceivedPayload(
                        input=enhanced_input,
                        inputs=payload.inputs,
                        session_id=payload.session_id,
                        component_id=payload.component_id,
                        component_type=payload.component_type
                    )

                    log.debug(f"Enhanced input with {len(knowledge_context)} knowledge items")
                    return enhanced_payload

        except Exception as e:
            log.debug(f"Knowledge enhancement failed: {e}")

        return payload

    def _capture_thought_hook(self, payload: AgentThoughtPayload) -> None:
        """Capture agent thoughts as knowledge in the graph."""
        if not self._neo4j_component:
            return

        try:
            log.debug(f"Capturing thought in knowledge graph: {payload.thought[:50]}...")

            # Create thought node with embedding
            thought_data = {
                "id": f"thought_{payload.component_id}_{hash(payload.thought)}",
                "thought": payload.thought,
                "component_id": payload.component_id,
                "timestamp": getattr(payload, 'timestamp', None)
            }

            self._neo4j_component.create_node("Thought", thought_data)

            # Extract concepts from the thought and create relationships
            concepts = self._extract_concepts_from_text(payload.thought)
            for concept in concepts:
                concept_data = {
                    "id": f"concept_{hash(concept)}",
                    "description": concept
                }

                # Create concept node if it doesn't exist
                self._neo4j_component.create_node("Concept", concept_data)

                # Create relationship between thought and concept
                self._neo4j_component.run_query(
                    "MATCH (t:Thought {id: $thought_id}), (c:Concept {id: $concept_id}) "
                    "MERGE (t)-[:RELATES_TO]->(c)",
                    {"thought_id": thought_data["id"], "concept_id": concept_data["id"]}
                )

        except Exception as e:
            log.debug(f"Thought capture failed: {e}")

    def _capture_action_hook(self, payload: AgentActionPayload) -> None:
        """Capture agent actions in the knowledge graph."""
        if not self._neo4j_component:
            return

        try:
            log.debug(f"Capturing action in knowledge graph: {payload.action[:50]}...")

            # Store action with context
            action_data = {
                "id": f"action_{payload.component_id}_{hash(payload.action)}",
                "action": payload.action,
                "component_id": payload.component_id,
                "timestamp": getattr(payload, 'timestamp', None)
            }

            self._neo4j_component.create_node("Action", action_data)

        except Exception as e:
            log.debug(f"Action capture failed: {e}")

    def _update_knowledge_hook(self, payload: AgentStepCompletePayload) -> None:
        """Update knowledge graph when agent completes a step."""
        if not self._neo4j_component:
            return

        try:
            log.debug(f"Updating knowledge graph for completed step: {payload.component_id}")

            # Create step completion record
            step_data = {
                "id": f"step_{payload.component_id}_{hash(str(payload))}",
                "component_id": payload.component_id,
                "result": getattr(payload, 'result', None),
                "timestamp": getattr(payload, 'timestamp', None)
            }

            self._neo4j_component.create_node("StepComplete", step_data)

        except Exception as e:
            log.debug(f"Knowledge update failed: {e}")

    def _extract_concepts_from_text(self, text: str) -> List[str]:
        """Extract key concepts from text (simple implementation)."""
        # Simple concept extraction - in practice you'd use NLP
        words = text.lower().split()
        concepts = []

        # Extract nouns and important terms (simplified)
        important_words = [word for word in words if len(word) > 4 and word.isalpha()]
        concepts.extend(important_words[:5])  # Top 5 concepts

        return list(set(concepts))  # Remove duplicates


# Auto-register the feature when module is imported
def _register_feature():
    from .base import InternalFeatureRegistry
    InternalFeatureRegistry.register("knowledge_graph", KnowledgeGraphFeature)

# Register when module is imported
_register_feature()