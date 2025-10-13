"""Integration tests for Knowledge Graph Feature - Demonstrates New Property Addition."""

import pytest
from unittest.mock import Mock, patch
from woodwork.components.internal_features import InternalFeatureRegistry, InternalComponentManager


@pytest.mark.integration
@pytest.mark.internal_features
class TestKnowledgeGraphFeature:
    """
    These tests demonstrate how easy it is to add a new agent property
    that spins up Neo4j components with custom hooks and pipes.
    """

    def setup_method(self):
        """Ensure knowledge graph feature is registered before each test."""
        from woodwork.components.internal_features.knowledge_graph import KnowledgeGraphFeature
        from woodwork.components.internal_features.base import InternalFeatureRegistry
        InternalFeatureRegistry.register("knowledge_graph", KnowledgeGraphFeature)

    @patch('woodwork.components.knowledge_bases.graph_databases.neo4j.neo4j')
    def test_knowledge_graph_feature_creation(self, mock_neo4j_factory):
        """Test that knowledge_graph: true creates the feature automatically."""
        # Setup mocks
        mock_neo4j_instance = Mock()
        mock_neo4j_factory.return_value = mock_neo4j_instance

        # This is all you need in your .ww config!
        config = {"knowledge_graph": True}

        # The system automatically creates the feature
        features = InternalFeatureRegistry.create_features(config)

        # Verify feature was created
        assert len(features) == 1
        assert features[0].__class__.__name__ == "KnowledgeGraphFeature"

        print("✓ knowledge_graph: true automatically creates KnowledgeGraphFeature")

    @patch('woodwork.components.knowledge_bases.graph_databases.neo4j.neo4j')
    def test_knowledge_graph_spins_up_neo4j_component(self, mock_neo4j_factory):
        """Test that the feature automatically creates Neo4j component."""
        # Setup mocks
        mock_neo4j_instance = Mock()
        mock_neo4j_factory.return_value = mock_neo4j_instance

        # Mock agent with knowledge_graph enabled
        mock_agent = Mock()
        mock_agent.name = "test_agent"

        # Mock model with API key
        mock_model = Mock()
        mock_model._api_key = "test-api-key"
        mock_agent.model = mock_model

        # Create feature and component manager
        component_manager = InternalComponentManager()
        features = InternalFeatureRegistry.create_features({"knowledge_graph": True})
        feature = features[0]

        # Setup feature (this creates the Neo4j component automatically)
        feature.setup(mock_agent, {"knowledge_graph": True}, component_manager)

        # Verify Neo4j component was created with correct config
        assert mock_neo4j_factory.call_count >= 1

        # Check that API key was passed to Neo4j
        call_kwargs = None
        for call in mock_neo4j_factory.call_args_list:
            if 'api_key' in call[1]:
                call_kwargs = call[1]
                break

        assert call_kwargs is not None
        assert "test-api-key" in call_kwargs["api_key"]
        assert "test_agent_knowledge_graph" in call_kwargs["name"]

        # Verify agent has knowledge graph attached
        assert hasattr(mock_agent, '_knowledge_graph')
        assert hasattr(mock_agent, '_knowledge_mode')
        assert mock_agent._knowledge_graph is mock_neo4j_instance
        assert mock_agent._knowledge_mode is True

        print("✓ Feature automatically creates and configures Neo4j component")

    def test_knowledge_graph_hooks_and_pipes(self):
        """Test that the feature provides intelligent hooks and pipes."""
        from woodwork.components.internal_features.knowledge_graph import KnowledgeGraphFeature

        feature = KnowledgeGraphFeature()

        # Check hooks - should capture thoughts, actions, and step completion
        hooks = feature.get_hooks()
        hook_events = [hook[0] for hook in hooks]

        assert "agent.thought" in hook_events
        assert "agent.action" in hook_events
        assert "agent.step_complete" in hook_events

        # Check pipes - should enhance input with knowledge
        pipes = feature.get_pipes()
        pipe_events = [pipe[0] for pipe in pipes]

        assert "input.received" in pipe_events

        print("✓ Feature provides intelligent hooks and pipes for knowledge management")

    @patch('woodwork.components.knowledge_bases.graph_databases.neo4j.neo4j')
    def test_complete_workflow_from_config_to_components(self, mock_neo4j_factory):
        """Test the complete workflow: config → feature → component → hooks/pipes."""
        # Setup mocks
        mock_neo4j_instance = Mock()
        mock_neo4j_instance.run_query = Mock()
        mock_neo4j_instance.create_node = Mock()
        mock_neo4j_instance.similarity_search = Mock(return_value=[])
        mock_neo4j_factory.return_value = mock_neo4j_instance

        # Mock agent
        mock_agent = Mock()
        mock_agent.name = "intelligent_agent"
        mock_model = Mock()
        mock_model._api_key = "test-key"
        mock_agent.model = mock_model

        # Step 1: Single line in config creates everything
        config = {"knowledge_graph": True}

        # Step 2: Feature system automatically handles the rest
        component_manager = InternalComponentManager()
        features = InternalFeatureRegistry.create_features(config)

        assert len(features) == 1
        feature = features[0]

        # Step 3: Setup creates components and registers hooks/pipes
        feature.setup(mock_agent, config, component_manager)

        # Verify complete setup
        assert mock_agent._knowledge_graph is mock_neo4j_instance
        assert mock_agent._knowledge_mode is True

        # Verify Neo4j schema initialization was called
        assert mock_neo4j_instance.run_query.call_count >= 1

        # Step 4: Test that hooks work by simulating events
        hooks = feature.get_hooks()
        pipes = feature.get_pipes()

        # Test thought capture hook
        from woodwork.types.events import AgentThoughtPayload
        thought_payload = AgentThoughtPayload(
            thought="I need to analyze this data carefully",
            component_id="intelligent_agent",
            component_type="agent"
        )

        thought_hook = None
        for event, hook_func in hooks:
            if event == "agent.thought":
                thought_hook = hook_func
                break

        assert thought_hook is not None
        thought_hook(thought_payload)

        # Verify thought was stored in Neo4j
        assert mock_neo4j_instance.create_node.called

        # Test input enhancement pipe
        from woodwork.types.events import InputReceivedPayload
        input_payload = InputReceivedPayload(
            input="How do I analyze data?",
            inputs=["How do I analyze data?"],
            session_id="test_session",
            component_id="intelligent_agent",
            component_type="agent"
        )

        enhancement_pipe = None
        for event, pipe_func in pipes:
            if event == "input.received":
                enhancement_pipe = pipe_func
                break

        assert enhancement_pipe is not None
        enhanced_payload = enhancement_pipe(input_payload)

        # Verify similarity search was called to enhance input
        assert mock_neo4j_instance.similarity_search.called

        print("✓ Complete workflow: config → feature → Neo4j → hooks/pipes working!")

    def test_easy_extension_pattern(self):
        """Demonstrate how easy it is to extend with new features."""

        # Here's how simple it is to add a new feature:
        print("\n" + "="*60)
        print("🚀 DEVELOPER EXPERIENCE DEMO:")
        print("="*60)

        print("\n1️⃣  CREATE FEATURE (~/my_feature.py):")
        print("""
class MyAwesomeFeature(InternalFeature):
    def get_required_components(self):
        return [{"component_type": "redis", "component_id": "cache", ...}]

    def _setup_feature(self, component, config, manager):
        # Auto-create Redis component
        redis = manager.get_or_create_component("cache", "redis", {...})
        component._my_cache = redis

    def get_hooks(self):
        return [("agent.action", self._cache_action)]

    def get_pipes(self):
        return [("input.received", self._enhance_from_cache)]
""")

        print("\n2️⃣  REGISTER FEATURE (one line):")
        print("""
InternalFeatureRegistry.register("my_awesome", MyAwesomeFeature)
""")

        print("\n3️⃣  USE IN CONFIG (one line):")
        print("""
my_agent = agent llm {
    my_awesome: true  # ← Creates Redis, registers hooks/pipes!
    model: my_llm
    tools: [...]
}
""")

        print("\n4️⃣  RESULT:")
        print("""
✅ Redis component automatically created and started
✅ Hooks automatically registered with UnifiedEventBus
✅ Pipes automatically registered for input enhancement
✅ Component accessible as agent._my_cache
✅ All from one line in config!
""")

        print("="*60)
        print("🎉 THAT'S IT! Adding new features is incredibly easy!")
        print("="*60)

        # Actual test
        from woodwork.components.internal_features.knowledge_graph import KnowledgeGraphFeature

        # Verify our new feature follows the same pattern
        feature = KnowledgeGraphFeature()

        # Has required components
        assert len(feature.get_required_components()) > 0

        # Has hooks and pipes
        assert len(feature.get_hooks()) > 0
        assert len(feature.get_pipes()) > 0

        print("\n✓ Knowledge graph feature follows the easy extension pattern!")