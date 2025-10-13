"""Unit tests for WorkflowsFeature with auto-component creation."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json
from woodwork.components.internal_features.workflows import WorkflowsFeature
from woodwork.types.events import AgentActionPayload, AgentStepCompletePayload, InputReceivedPayload


@pytest.mark.unit
@pytest.mark.workflows
class TestWorkflowsFeature:
    """Test suite for WorkflowsFeature functionality."""

    @pytest.fixture
    def workflows_feature(self):
        """Create a WorkflowsFeature instance for testing."""
        return WorkflowsFeature()

    @pytest.fixture
    def mock_component(self):
        """Create a mock component with model and API key."""
        component = Mock()
        component.name = "test_agent"
        component.model = Mock()
        component.model._api_key = "test-api-key"
        return component

    @pytest.fixture
    def mock_neo4j(self):
        """Create a mock Neo4j component."""
        neo4j = Mock()
        neo4j.init_vector_index = Mock()
        neo4j.run = Mock(return_value=[])
        neo4j.similarity_search = Mock(return_value=[])
        return neo4j

    @pytest.fixture
    def mock_component_manager(self, mock_neo4j):
        """Create a mock component manager."""
        manager = Mock()
        manager.get_or_create_component = Mock(return_value=mock_neo4j)
        return manager

    def test_init(self, workflows_feature):
        """Test WorkflowsFeature initialization."""
        assert workflows_feature._neo4j_component is None
        assert workflows_feature._component_ref is None
        assert workflows_feature._current_workflow_id is None
        assert workflows_feature._workflow_actions == []

    def test_get_required_components(self, workflows_feature):
        """Test that required components are properly defined."""
        components = workflows_feature.get_required_components()

        assert len(components) == 1
        assert components[0]["component_type"] == "neo4j"
        assert components[0]["component_id"] == "workflows_neo4j"
        assert components[0]["optional"] is False
        assert "uri" in components[0]["config"]

    def test_setup_feature_success(self, workflows_feature, mock_component, mock_component_manager, mock_neo4j):
        """Test successful feature setup with Neo4j component creation."""
        config = {
            "workflows_uri": "bolt://localhost:7687",
            "workflows_user": "neo4j",
            "workflows_password": "testpass"
        }

        workflows_feature._setup_feature(mock_component, config, mock_component_manager)

        # Verify component manager was called to create Neo4j
        mock_component_manager.get_or_create_component.assert_called_once()
        call_args = mock_component_manager.get_or_create_component.call_args
        assert call_args[1]["component_id"] == "test_agent_workflows_neo4j"
        assert call_args[1]["component_type"] == "neo4j"
        assert call_args[1]["config"]["api_key"] == "test-api-key"

        # Verify vector indices were initialized
        assert mock_neo4j.init_vector_index.call_count == 2

        # Verify component attributes were set
        assert hasattr(mock_component, '_workflows_db')
        assert hasattr(mock_component, '_workflows_mode')
        assert mock_component._workflows_db is mock_neo4j
        assert mock_component._workflows_mode is True

    def test_setup_feature_no_api_key(self, workflows_feature, mock_component_manager):
        """Test feature setup fails without API key."""
        component = Mock()
        component.name = "test_agent"
        component.model = Mock()
        # No _api_key attribute

        config = {}

        with pytest.raises(TypeError, match="Workflows feature requires API key"):
            workflows_feature._setup_feature(component, config, mock_component_manager)

    def test_teardown(self, workflows_feature, mock_component, mock_component_manager, mock_neo4j):
        """Test feature teardown cleans up properly."""
        # Setup first
        workflows_feature._setup_feature(mock_component, {}, mock_component_manager)
        workflows_feature._current_workflow_id = "test-workflow"
        workflows_feature._workflow_actions = [{"test": "action"}]

        # Teardown
        workflows_feature.teardown(mock_component, mock_component_manager)

        # Verify cleanup
        assert not hasattr(mock_component, '_workflows_db')
        assert not hasattr(mock_component, '_workflows_mode')
        assert workflows_feature._neo4j_component is None
        assert workflows_feature._current_workflow_id is None
        assert workflows_feature._workflow_actions == []

    def test_get_hooks(self, workflows_feature):
        """Test that hooks are properly defined."""
        hooks = workflows_feature.get_hooks()

        assert len(hooks) == 2
        hook_events = [hook[0] for hook in hooks]
        assert "agent.action" in hook_events
        assert "agent.step_complete" in hook_events

    def test_get_pipes(self, workflows_feature):
        """Test that pipes are properly defined."""
        pipes = workflows_feature.get_pipes()

        assert len(pipes) == 1
        assert pipes[0][0] == "input.received"

    def test_check_similar_workflows_pipe_no_match(self, workflows_feature, mock_component, mock_component_manager, mock_neo4j):
        """Test input pipe when no similar workflows found."""
        # Setup
        workflows_feature._setup_feature(mock_component, {}, mock_component_manager)
        mock_neo4j.similarity_search.return_value = []

        # Test payload
        payload = InputReceivedPayload(
            input="How do I create a file?",
            inputs={},
            session_id="test",
            component_id="test_agent",
            component_type="agent"
        )

        # Execute pipe
        result = workflows_feature._check_similar_workflows_pipe(payload)

        # Should return unmodified payload
        assert result.input == payload.input
        assert workflows_feature._current_workflow_id is not None  # New workflow started

    def test_check_similar_workflows_pipe_with_match(self, workflows_feature, mock_component, mock_component_manager, mock_neo4j):
        """Test input pipe when similar workflow found."""
        # Setup
        workflows_feature._setup_feature(mock_component, {}, mock_component_manager)

        # Mock similarity search result
        mock_neo4j.similarity_search.return_value = [
            {"nodeID": "prompt-123", "score": 0.9, "text": "How to create a file"}
        ]

        # Mock workflow context query
        mock_neo4j.run.return_value = [
            {
                "prompt": "How to create a file",
                "workflow": [
                    {"tool": "file_tool", "action": "create", "output": "file_created"},
                    {"tool": "text_tool", "action": "write", "output": "content_added"}
                ]
            }
        ]

        # Test payload
        payload = InputReceivedPayload(
            input="How do I create a file?",
            inputs={},
            session_id="test",
            component_id="test_agent",
            component_type="agent"
        )

        # Execute pipe
        result = workflows_feature._check_similar_workflows_pipe(payload)

        # Should have enhanced input with workflow context
        assert "[Similar Workflow Context]:" in result.input
        assert "Use file_tool to create" in result.input

    def test_sync_action_hook(self, workflows_feature, mock_component, mock_component_manager, mock_neo4j):
        """Test action sync hook creates proper graph nodes."""
        # Setup
        workflows_feature._setup_feature(mock_component, {}, mock_component_manager)
        workflows_feature._current_workflow_id = "test-workflow"

        # Test payload
        action_data = {
            "tool": "file_tool",
            "action": "create",
            "inputs": {"filename": "test.txt"},
            "output": "file_created"
        }

        payload = AgentActionPayload(
            action=json.dumps(action_data),
            component_id="test_agent",
            component_type="agent"
        )

        # Execute hook
        workflows_feature._sync_action_hook(payload)

        # Verify Neo4j queries were called
        assert mock_neo4j.run.call_count >= 1

        # Verify action was tracked
        assert len(workflows_feature._workflow_actions) == 1
        assert workflows_feature._workflow_actions[0]["tool"] == "file_tool"

    def test_complete_workflow_hook(self, workflows_feature, mock_component, mock_component_manager, mock_neo4j):
        """Test workflow completion hook."""
        # Setup
        workflows_feature._setup_feature(mock_component, {}, mock_component_manager)
        workflows_feature._current_workflow_id = "test-workflow"

        # Test payload
        payload = AgentStepCompletePayload(
            result="Task completed successfully",
            component_id="test_agent",
            component_type="agent"
        )

        # Execute hook
        workflows_feature._complete_workflow_hook(payload)

        # Verify workflow was completed
        mock_neo4j.run.assert_called()
        assert workflows_feature._current_workflow_id is None
        assert workflows_feature._workflow_actions == []

    def test_start_new_workflow(self, workflows_feature, mock_component, mock_component_manager, mock_neo4j):
        """Test starting a new workflow creates proper nodes."""
        # Setup
        workflows_feature._setup_feature(mock_component, {}, mock_component_manager)

        # Start workflow
        workflows_feature._start_new_workflow("Test input")

        # Verify workflow ID was generated
        assert workflows_feature._current_workflow_id is not None
        assert workflows_feature._workflow_actions == []

        # Verify Neo4j queries were called
        mock_neo4j.run.assert_called()

    def test_create_action_relationships_no_dependencies(self, workflows_feature, mock_component, mock_component_manager, mock_neo4j):
        """Test action relationship creation when no dependencies."""
        # Setup
        workflows_feature._setup_feature(mock_component, {}, mock_component_manager)
        workflows_feature._current_workflow_id = "test-workflow"

        # Create first action (should link to prompt)
        workflows_feature._create_action_relationships(
            "action_1",
            {"filename": "test.txt"},
            "file_created"
        )

        # Verify STARTS relationship was created
        mock_neo4j.run.assert_called()

    def test_create_action_relationships_with_dependencies(self, workflows_feature, mock_component, mock_component_manager, mock_neo4j):
        """Test action relationship creation with input dependencies."""
        # Setup
        workflows_feature._setup_feature(mock_component, {}, mock_component_manager)
        workflows_feature._current_workflow_id = "test-workflow"
        workflows_feature._workflow_actions = [
            {"id": "action_1", "output": "file_created", "tool": "file_tool", "action": "create", "inputs": {}}
        ]

        # Create second action that depends on first
        workflows_feature._create_action_relationships(
            "action_2",
            {"file": "file_created"},  # Depends on previous action's output
            "content_added"
        )

        # Verify DEPENDS_ON and NEXT relationships were created
        assert mock_neo4j.run.call_count >= 2

    def test_extract_api_key(self, workflows_feature):
        """Test API key extraction from component."""
        # Component with API key
        component_with_key = Mock()
        component_with_key.model = Mock()
        component_with_key.model._api_key = "test-key"

        assert workflows_feature._extract_api_key(component_with_key) == "test-key"

        # Component without API key
        component_no_key = Mock()
        component_no_key.model = Mock()
        # No _api_key attribute

        assert workflows_feature._extract_api_key(component_no_key) is None

    def test_get_workflow_context(self, workflows_feature, mock_component, mock_component_manager, mock_neo4j):
        """Test workflow context retrieval."""
        # Setup
        workflows_feature._setup_feature(mock_component, {}, mock_component_manager)

        # Mock query result
        mock_neo4j.run.return_value = [
            {
                "prompt": "Create a file",
                "workflow": [
                    {"tool": "file_tool", "action": "create", "output": "file_created"},
                    {"tool": "text_tool", "action": "write", "output": "content_added"}
                ]
            }
        ]

        # Get context
        context = workflows_feature._get_workflow_context("prompt-123")

        # Verify context format
        assert "Use file_tool to create" in context
        assert "Use text_tool to write" in context

    def test_feature_registration(self):
        """Test that feature is properly registered."""
        from woodwork.components.internal_features.base import InternalFeatureRegistry

        # Should be registered
        assert "workflows" in InternalFeatureRegistry._registry
        assert InternalFeatureRegistry._registry["workflows"] == WorkflowsFeature