"""
import pytest
Unit tests for unified WorkflowsFeature (merging graph_cache + workflows).

Following TDD - these tests are written BEFORE implementation.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from dataclasses import replace
import json


@pytest.mark.slow
class TestUnifiedWorkflowsFeature:
    """Test unified workflows feature with all functionality."""

    @pytest.fixture
    def mock_component(self):
        """Mock agent component."""
        component = Mock()
        component.name = "test_agent"
        component.model = Mock()
        component.model._api_key = "test-api-key"
        component.session_id = "test_session"
        return component

    @pytest.fixture
    def mock_neo4j(self):
        """Mock Neo4j component."""
        neo4j = Mock()
        neo4j.init_vector_index = Mock()
        neo4j.run = Mock(return_value=[])
        neo4j.similarity_search = Mock(return_value=[])
        neo4j.create_node = Mock()
        return neo4j

    @pytest.fixture
    def mock_component_manager(self):
        """Mock internal component manager."""
        manager = Mock()
        manager.get_or_create_component = Mock()
        return manager

    @pytest.fixture
    def mock_workflow_executor(self):
        """Mock workflow executor."""
        executor = Mock()
        executor.execute_workflow = AsyncMock(return_value={"status": "completed"})
        return executor

    @pytest.fixture
    def feature(self):
        """Create WorkflowsFeature instance."""
        from woodwork.components.internal_features.workflows import WorkflowsFeature
        return WorkflowsFeature()

    def test_feature_initialization(self, feature):
        """Test that feature initializes correctly."""
        assert feature._neo4j_component is None
        assert feature._component_ref is None
        assert feature._current_workflow_id is None
        assert feature._workflow_actions == []

    def test_get_required_components_returns_neo4j(self, feature):
        """Test that feature specifies required Neo4j component."""
        required = feature.get_required_components()

        assert len(required) == 1
        assert required[0]['component_type'] == 'neo4j'
        assert 'workflows_neo4j' in required[0]['component_id']
        assert not required[0]['optional']

    def test_setup_feature_creates_neo4j_component(self, feature, mock_component, mock_neo4j, mock_component_manager):
        """Test that setup creates Neo4j component through manager."""
        mock_component_manager.get_or_create_component.return_value = mock_neo4j

        feature._setup_feature(mock_component, {}, mock_component_manager)

        # Verify component manager was called
        mock_component_manager.get_or_create_component.assert_called_once()
        call_args = mock_component_manager.get_or_create_component.call_args

        assert 'neo4j' in str(call_args)
        assert mock_component._workflows_db == mock_neo4j
        assert mock_component._workflows_mode is True

    def test_setup_feature_initializes_vector_indices(self, feature, mock_component, mock_neo4j, mock_component_manager):
        """Test that setup initializes vector indices for prompts and actions."""
        mock_component_manager.get_or_create_component.return_value = mock_neo4j

        feature._setup_feature(mock_component, {}, mock_component_manager)

        # Verify vector indices initialized
        assert mock_neo4j.init_vector_index.call_count >= 2

        # Check for prompt and action indices
        calls = [str(call) for call in mock_neo4j.init_vector_index.call_args_list]
        assert any('Prompt' in call for call in calls)
        assert any('Action' in call for call in calls)

    def test_setup_feature_initializes_graph_schema(self, feature, mock_component, mock_neo4j, mock_component_manager):
        """Test that setup initializes graph schema with constraints."""
        mock_component_manager.get_or_create_component.return_value = mock_neo4j

        feature._setup_feature(mock_component, {}, mock_component_manager)

        # Verify schema queries were run
        assert mock_neo4j.run.called

        # Check for constraint creation
        calls = [str(call) for call in mock_neo4j.run.call_args_list]
        schema_calls = [c for c in calls if 'CONSTRAINT' in c or 'INDEX' in c]
        assert len(schema_calls) > 0

    def test_setup_feature_raises_without_api_key(self, feature, mock_component_manager):
        """Test that setup fails without API key from model."""
        component = Mock()
        component.name = "test"
        component.model = Mock(spec=[])  # No _api_key attribute

        with pytest.raises(TypeError, match="requires API key"):
            feature._setup_feature(component, {}, mock_component_manager)

    def test_setup_feature_uses_custom_config(self, feature, mock_component, mock_neo4j, mock_component_manager):
        """Test that custom workflow config is used."""
        mock_component_manager.get_or_create_component.return_value = mock_neo4j

        config = {
            "workflows_uri": "bolt://custom:7687",
            "workflows_user": "custom_user",
            "workflows_password": "custom_pass"
        }

        feature._setup_feature(mock_component, config, mock_component_manager)

        call_args = mock_component_manager.get_or_create_component.call_args
        neo4j_config = call_args[1]['config']

        assert neo4j_config['uri'] == "bolt://custom:7687"
        assert neo4j_config['user'] == "custom_user"
        assert neo4j_config['password'] == "custom_pass"

    def test_teardown_removes_component_references(self, feature, mock_component, mock_component_manager):
        """Test that teardown removes component references."""
        # Setup first
        mock_component._workflows_db = Mock()
        mock_component._workflows_mode = True
        feature._neo4j_component = Mock()

        # Teardown
        feature.teardown(mock_component, mock_component_manager)

        assert not hasattr(mock_component, '_workflows_db')
        assert not hasattr(mock_component, '_workflows_mode')
        assert feature._neo4j_component is None

    def test_get_hooks_returns_expected_events(self, feature):
        """Test that feature registers expected hooks."""
        hooks = feature.get_hooks()

        hook_events = [event for event, _ in hooks]
        assert 'agent.action' in hook_events
        assert 'agent.step_complete' in hook_events

    def test_get_pipes_returns_input_pipe(self, feature):
        """Test that feature registers input pipe for similarity check."""
        pipes = feature.get_pipes()

        pipe_events = [event for event, _ in pipes]
        assert 'input.received' in pipe_events

    def test_start_new_workflow_creates_nodes(self, feature, mock_neo4j):
        """Test that _start_new_workflow creates Workflow and Prompt nodes."""
        feature._neo4j_component = mock_neo4j
        feature._component_ref = Mock()
        feature._component_ref.name = "test_agent"
        feature._component_ref.model = Mock()
        feature._component_ref.model._api_key = "test-key"

        feature._start_new_workflow("Test input prompt")

        # Verify workflow was created in Neo4j
        assert mock_neo4j.run.called
        call_args = str(mock_neo4j.run.call_args_list)

        assert 'Workflow' in call_args
        assert 'Prompt' in call_args
        assert feature._current_workflow_id is not None

    def test_sync_action_hook_creates_action_node(self, feature, mock_neo4j):
        """Test that _sync_action_hook creates Action node in graph."""
        from woodwork.types.events import AgentActionPayload

        feature._neo4j_component = mock_neo4j
        feature._component_ref = Mock()
        feature._component_ref.name = "test_agent"
        feature._component_ref.model = Mock()
        feature._component_ref.model._api_key = "test-key"
        feature._current_workflow_id = "w1"

        action_data = {
            "tool": "file_tool",
            "action": "read",
            "inputs": {"path": "test.txt"},
            "output": "file_content"
        }

        payload = AgentActionPayload(
            action=json.dumps(action_data),
            component_id="test_agent",
            component_type="agent"
        )

        feature._sync_action_hook(payload)

        # Verify action node created
        assert mock_neo4j.run.called
        call_args = str(mock_neo4j.run.call_args_list)

        assert 'Action' in call_args
        assert 'file_tool' in call_args
        assert len(feature._workflow_actions) == 1

    def test_sync_action_hook_tracks_dependencies(self, feature, mock_neo4j):
        """Test that action syncing tracks dependencies between actions."""
        from woodwork.types.events import AgentActionPayload

        feature._neo4j_component = mock_neo4j
        feature._component_ref = Mock()
        feature._component_ref.name = "test_agent"
        feature._component_ref.model = Mock()
        feature._component_ref.model._api_key = "test-key"
        feature._current_workflow_id = "w1"

        # First action
        action1_data = {
            "tool": "file_tool",
            "action": "read",
            "inputs": {},
            "output": "file_data"
        }

        payload1 = AgentActionPayload(
            action=json.dumps(action1_data),
            component_id="test_agent",
            component_type="agent"
        )

        feature._sync_action_hook(payload1)

        # Second action that depends on first
        action2_data = {
            "tool": "process_tool",
            "action": "process",
            "inputs": {"data": "file_data"},  # References first action's output
            "output": "result"
        }

        payload2 = AgentActionPayload(
            action=json.dumps(action2_data),
            component_id="test_agent",
            component_type="agent"
        )

        feature._sync_action_hook(payload2)

        # Verify dependency relationship created
        assert len(feature._workflow_actions) == 2

        # Check that DEPENDS_ON or NEXT relationship was created
        call_args = str(mock_neo4j.run.call_args_list)
        assert 'DEPENDS_ON' in call_args or 'NEXT' in call_args

    def test_complete_workflow_hook_marks_complete(self, feature, mock_neo4j):
        """Test that _complete_workflow_hook marks workflow as completed."""
        from woodwork.types.events import AgentStepCompletePayload

        feature._neo4j_component = mock_neo4j
        feature._current_workflow_id = "w1"
        feature._workflow_actions = [{"id": "a1"}]

        payload = AgentStepCompletePayload(
            step=5,
            session_id="test_session",
            component_id="test_agent",
            component_type="agent"
        )

        feature._complete_workflow_hook(payload)

        # Verify workflow marked as completed
        assert mock_neo4j.run.called
        call_args = str(mock_neo4j.run.call_args_list)

        assert 'completed' in call_args

        # Verify state reset
        assert feature._current_workflow_id is None
        assert feature._workflow_actions == []

    def test_check_similar_workflows_pipe_without_matches(self, feature, mock_neo4j):
        """Test similarity pipe with no matching workflows."""
        from woodwork.types.events import InputReceivedPayload

        feature._neo4j_component = mock_neo4j
        feature._component_ref = Mock()
        feature._component_ref.name = "test_agent"
        feature._component_ref.model = Mock()
        feature._component_ref.model._api_key = "test-key"

        mock_neo4j.similarity_search.return_value = []

        payload = InputReceivedPayload(
            input="Test input",
            inputs={},
            session_id="test",
            component_id="agent",
            component_type="agent"
        )

        result = feature._check_similar_workflows_pipe(payload)

        # Should start new workflow
        assert feature._current_workflow_id is not None
        assert result.input == "Test input"  # No modification

    def test_check_similar_workflows_pipe_with_low_similarity(self, feature, mock_neo4j):
        """Test similarity pipe with low similarity match (below threshold)."""
        from woodwork.types.events import InputReceivedPayload

        feature._neo4j_component = mock_neo4j
        feature._component_ref = Mock()
        feature._component_ref.name = "test_agent"
        feature._component_ref.model = Mock()
        feature._component_ref.model._api_key = "test-key"

        # Low similarity match (below 0.75 threshold)
        mock_neo4j.similarity_search.return_value = [
            {"nodeID": "p1", "score": 0.5, "text": "Different task"}
        ]

        payload = InputReceivedPayload(
            input="Test input",
            inputs={},
            session_id="test",
            component_id="agent",
            component_type="agent"
        )

        result = feature._check_similar_workflows_pipe(payload)

        # Should not inject context due to low similarity
        assert "[Available Similar Workflows]" not in result.input

    def test_extract_api_key_from_component(self, feature):
        """Test _extract_api_key gets API key from component model."""
        component = Mock()
        component.model = Mock()
        component.model._api_key = "my-secret-key"

        api_key = feature._extract_api_key(component)

        assert api_key == "my-secret-key"

    def test_extract_api_key_returns_none_without_model(self, feature):
        """Test _extract_api_key returns None when model has no API key."""
        component = Mock(spec=[])

        api_key = feature._extract_api_key(component)

        assert api_key is None

    def test_get_workflow_detail_queries_neo4j(self, feature, mock_neo4j):
        """Test _get_workflow_detail retrieves workflow data."""
        feature._neo4j_component = mock_neo4j

        mock_neo4j.run.return_value = [
            {
                "prompt": "Test prompt",
                "workflow": [
                    {"tool": "t1", "action": "a1", "output": "o1"}
                ]
            }
        ]

        result = feature._get_workflow_context("prompt_node_id")

        # Should format workflow context
        assert result is not None

    def test_create_action_relationships_creates_next_relationship(self, feature, mock_neo4j):
        """Test that sequential actions get NEXT relationship."""
        feature._neo4j_component = mock_neo4j
        feature._workflow_actions = [
            {"id": "a1", "output": "result1"}
        ]

        feature._create_action_relationships("a2", {}, "result2")

        # Verify NEXT relationship created
        call_args = str(mock_neo4j.run.call_args_list)
        assert 'NEXT' in call_args

    def test_create_action_relationships_creates_depends_on(self, feature, mock_neo4j):
        """Test that dependent actions get DEPENDS_ON relationship."""
        feature._neo4j_component = mock_neo4j
        feature._workflow_actions = [
            {"id": "a1", "output": "data"}
        ]

        # Action that uses previous output as input
        feature._create_action_relationships("a2", {"input": "data"}, "result")

        # Verify DEPENDS_ON relationship created
        call_args = str(mock_neo4j.run.call_args_list)
        assert 'DEPENDS_ON' in call_args

    def test_create_action_relationships_links_first_to_prompt(self, feature, mock_neo4j):
        """Test that first action gets linked to prompt with STARTS."""
        feature._neo4j_component = mock_neo4j
        feature._current_workflow_id = "w1"
        feature._workflow_actions = []  # No previous actions

        feature._create_action_relationships("a1", {}, "result")

        # Verify STARTS relationship created
        call_args = str(mock_neo4j.run.call_args_list)
        assert 'STARTS' in call_args
