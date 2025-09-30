"""Unit tests for GraphCacheFeature."""

import pytest
from unittest.mock import Mock, patch
from woodwork.components.internal_features import InternalComponentManager
from woodwork.components.internal_features.graph_cache import GraphCacheFeature


@pytest.mark.unit
@pytest.mark.internal_features
@pytest.mark.graph_cache
class TestGraphCacheFeature:
    @pytest.fixture
    def mock_component(self):
        component = Mock()
        component.name = "test_agent"
        model = Mock()
        model._api_key = "test-api-key"
        component.model = model
        return component

    @pytest.fixture
    def mock_component_without_api_key(self):
        component = Mock()
        component.name = "test_agent"
        component.model = Mock(spec=[])  # No _api_key attribute
        return component

    @pytest.fixture
    def mock_component_manager(self):
        manager = Mock(spec=InternalComponentManager)
        mock_neo4j = Mock()
        manager.get_or_create_component.return_value = mock_neo4j
        return manager

    @pytest.fixture
    def graph_cache_feature(self):
        return GraphCacheFeature()

    def test_get_required_components(self, graph_cache_feature):
        """Test that feature specifies required Neo4j component."""
        required = graph_cache_feature.get_required_components()

        assert len(required) == 1
        assert required[0]["component_type"] == "neo4j"
        assert required[0]["component_id"] == "graph_cache_neo4j"
        assert not required[0]["optional"]
        assert "uri" in required[0]["config"]

    def test_setup_creates_neo4j_component_via_manager(self, graph_cache_feature, mock_component, mock_component_manager):
        """Test that setup creates Neo4j component through component manager."""
        config = {"graph_cache": True}

        graph_cache_feature.setup(mock_component, config, mock_component_manager)

        # Verify component manager was called to create Neo4j component
        mock_component_manager.get_or_create_component.assert_called_once()
        call_args = mock_component_manager.get_or_create_component.call_args
        assert call_args[1]["component_type"] == "neo4j"
        assert "test_agent_cache" in call_args[1]["config"]["name"]
        assert call_args[1]["config"]["api_key"] == "test-api-key"

        assert hasattr(mock_component, '_graph_cache')
        assert mock_component._cache_mode is True

    def test_setup_with_custom_config(self, graph_cache_feature, mock_component, mock_component_manager):
        """Test setup with custom graph cache configuration."""
        config = {
            "graph_cache": True,
            "graph_cache_uri": "bolt://custom:7687",
            "graph_cache_user": "custom_user",
            "graph_cache_password": "custom_pass"
        }

        graph_cache_feature.setup(mock_component, config, mock_component_manager)

        call_args = mock_component_manager.get_or_create_component.call_args
        config_used = call_args[1]["config"]
        assert config_used["uri"] == "bolt://custom:7687"
        assert config_used["user"] == "custom_user"
        assert config_used["password"] == "custom_pass"

    def test_setup_requires_api_key(self, graph_cache_feature, mock_component_without_api_key, mock_component_manager):
        """Test that setup fails without API key."""
        config = {"graph_cache": True}

        with pytest.raises(TypeError, match="Graph cache requires API key"):
            graph_cache_feature.setup(mock_component_without_api_key, config, mock_component_manager)

    def test_setup_handles_vector_index_initialization(self, graph_cache_feature, mock_component, mock_component_manager):
        """Test that setup handles vector index initialization properly."""
        mock_neo4j = Mock()
        mock_component_manager.get_or_create_component.return_value = mock_neo4j
        config = {"graph_cache": True}

        graph_cache_feature.setup(mock_component, config, mock_component_manager)

        mock_neo4j.init_vector_index.assert_called_once_with(
            index_name="embeddings",
            label="Prompt",
            property="embedding"
        )

    def test_setup_handles_vector_index_exception(self, graph_cache_feature, mock_component, mock_component_manager):
        """Test that setup handles vector index initialization exceptions."""
        mock_neo4j = Mock()
        mock_neo4j.init_vector_index.side_effect = Exception("Index already exists")
        mock_component_manager.get_or_create_component.return_value = mock_neo4j
        config = {"graph_cache": True}

        # Should not raise exception
        graph_cache_feature.setup(mock_component, config, mock_component_manager)

    def test_teardown_removes_component_references(self, graph_cache_feature, mock_component, mock_component_manager):
        """Test that teardown removes component references but leaves cleanup to manager."""
        # Setup first
        config = {"graph_cache": True}
        graph_cache_feature.setup(mock_component, config, mock_component_manager)

        # Teardown
        graph_cache_feature.teardown(mock_component, mock_component_manager)

        assert not hasattr(mock_component, '_graph_cache')
        assert not hasattr(mock_component, '_cache_mode')

    def test_get_hooks_returns_expected_events(self, graph_cache_feature):
        """Test that feature registers expected hooks."""
        hooks = graph_cache_feature.get_hooks()

        hook_events = [event for event, _ in hooks]
        assert "agent.action" in hook_events
        assert "agent.step_complete" in hook_events

    def test_get_pipes_returns_expected_events(self, graph_cache_feature):
        """Test that feature registers expected pipes."""
        pipes = graph_cache_feature.get_pipes()

        pipe_events = [event for event, _ in pipes]
        assert "input.received" in pipe_events

    def test_cache_pipe_modifies_payload_on_hit(self, graph_cache_feature):
        """Test that cache pipe modifies payload when cache hit occurs."""
        # Setup mock Neo4j component with high-confidence result
        mock_neo4j = Mock()
        mock_neo4j.similarity_search.return_value = [{"score": 0.95, "actions": ["cached_action"]}]
        graph_cache_feature._neo4j_component = mock_neo4j

        from woodwork.types.events import InputReceivedPayload
        payload = InputReceivedPayload(input="test query")

        result = graph_cache_feature._check_cache_pipe(payload)

        assert result.cache_hit is True
        assert hasattr(result, 'cached_actions')
        assert result.cached_actions == ["cached_action"]

    def test_cache_pipe_no_modification_on_low_score(self, graph_cache_feature):
        """Test that cache pipe doesn't modify payload on low confidence."""
        mock_neo4j = Mock()
        mock_neo4j.similarity_search.return_value = [{"score": 0.5, "actions": ["cached_action"]}]
        graph_cache_feature._neo4j_component = mock_neo4j

        from woodwork.types.events import InputReceivedPayload
        payload = InputReceivedPayload(input="test query")

        result = graph_cache_feature._check_cache_pipe(payload)

        assert not hasattr(result, 'cache_hit') or not result.cache_hit

    def test_cache_pipe_handles_no_neo4j_component(self, graph_cache_feature):
        """Test that cache pipe handles missing Neo4j component."""
        from woodwork.types.events import InputReceivedPayload
        payload = InputReceivedPayload(input="test query")

        result = graph_cache_feature._check_cache_pipe(payload)

        # Should return unchanged payload
        assert result.input == "test query"

    def test_cache_pipe_handles_similarity_search_exception(self, graph_cache_feature):
        """Test that cache pipe handles similarity search exceptions."""
        mock_neo4j = Mock()
        mock_neo4j.similarity_search.side_effect = Exception("Search failed")
        graph_cache_feature._neo4j_component = mock_neo4j

        from woodwork.types.events import InputReceivedPayload
        payload = InputReceivedPayload(input="test query")

        result = graph_cache_feature._check_cache_pipe(payload)

        # Should return unchanged payload
        assert result.input == "test query"

    def test_log_action_hook(self, graph_cache_feature):
        """Test action logging hook."""
        mock_neo4j = Mock()
        graph_cache_feature._neo4j_component = mock_neo4j

        from woodwork.types.events import AgentActionPayload
        payload = AgentActionPayload(action="test action")

        graph_cache_feature._log_action_hook(payload)

        mock_neo4j.create_node.assert_called_once()
        call_args = mock_neo4j.create_node.call_args
        assert call_args[0][0] == "Action"
        assert call_args[0][1]["action"] == "test action"

    def test_cache_workflow_hook(self, graph_cache_feature):
        """Test workflow caching hook."""
        mock_neo4j = Mock()
        graph_cache_feature._neo4j_component = mock_neo4j

        from woodwork.types.events import AgentStepCompletePayload
        payload = AgentStepCompletePayload()

        graph_cache_feature._cache_workflow_hook(payload)

        mock_neo4j.create_node.assert_called_once()
        call_args = mock_neo4j.create_node.call_args
        assert call_args[0][0] == "Workflow"