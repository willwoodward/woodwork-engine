"""
Unit tests for workflow tools registration and top-3 context injection.

Following TDD - these tests are written to verify Phase 2 implementation.
"""

import pytest
from unittest.mock import Mock, AsyncMock
import json
from dataclasses import replace


class TestWorkflowToolsRegistration:
    """Test that workflows are registered as agent tools."""

    @pytest.fixture
    def mock_component(self):
        """Mock agent component."""
        component = Mock()
        component.name = "test_agent"
        component.session_id = "test_session"
        component.model = Mock()
        component.model._api_key = "test-key"
        component.task_m = Mock()  # Task master available
        return component

    @pytest.fixture
    def mock_neo4j(self):
        """Mock Neo4j component."""
        neo4j = Mock()
        neo4j.init_vector_index = Mock()
        neo4j.run = Mock(return_value=[])
        neo4j.similarity_search = Mock(return_value=[])
        return neo4j

    @pytest.fixture
    def mock_component_manager(self):
        """Mock component manager."""
        manager = Mock()
        manager.get_or_create_component = Mock()
        return manager

    @pytest.fixture
    def feature(self, mock_component, mock_neo4j, mock_component_manager):
        """Create and setup WorkflowsFeature."""
        from woodwork.components.internal_features.workflows import WorkflowsFeature

        feature = WorkflowsFeature()
        mock_component_manager.get_or_create_component.return_value = mock_neo4j

        feature._setup_feature(mock_component, {}, mock_component_manager)

        return feature

    def test_get_tools_returns_execute_workflow(self, feature):
        """Test that get_tools() returns execute_workflow tool."""
        tools = feature.get_tools()

        assert len(tools) >= 1

        execute_workflow_tool = next(
            (t for t in tools if t['name'] == 'execute_workflow'),
            None
        )

        assert execute_workflow_tool is not None
        assert 'description' in execute_workflow_tool
        assert 'parameters' in execute_workflow_tool
        assert 'function' in execute_workflow_tool

    def test_execute_workflow_tool_has_correct_parameters(self, feature):
        """Test that execute_workflow tool has workflow_id and inputs parameters."""
        tools = feature.get_tools()

        execute_workflow_tool = next(
            (t for t in tools if t['name'] == 'execute_workflow'),
            None
        )

        params = execute_workflow_tool['parameters']

        assert 'workflow_id' in params
        assert 'inputs' in params
        assert params['workflow_id']['type'] == 'string'
        assert params['inputs']['type'] == 'object'

    def test_get_tools_returns_empty_without_executor(self):
        """Test that get_tools() returns empty list if no executor."""
        from woodwork.components.internal_features.workflows import WorkflowsFeature

        feature = WorkflowsFeature()
        # No setup, so no executor

        tools = feature.get_tools()

        assert tools == []

    @pytest.mark.asyncio
    async def test_execute_workflow_tool_calls_executor(self, feature, mock_neo4j):
        """Test that execute_workflow tool calls the workflow executor."""
        # Mock workflow executor
        feature._workflow_executor = Mock()
        feature._workflow_executor.execute_workflow = AsyncMock(
            return_value={"status": "completed", "results": []}
        )

        # Get the tool function
        tools = feature.get_tools()
        execute_workflow_tool = next(
            (t for t in tools if t['name'] == 'execute_workflow'),
            None
        )

        tool_function = execute_workflow_tool['function']

        # Execute the tool
        result = await tool_function(
            workflow_id="w123",
            inputs={"test": "input"}
        )

        # Verify executor was called
        feature._workflow_executor.execute_workflow.assert_called_once()
        call_args = feature._workflow_executor.execute_workflow.call_args

        assert call_args[0][0] == "w123"  # workflow_id
        assert call_args[0][1] == {"test": "input"}  # inputs
        assert result['status'] == 'completed'

    @pytest.mark.asyncio
    async def test_execute_workflow_tool_raises_without_executor(self):
        """Test that execute_workflow tool raises error without executor."""
        from woodwork.components.internal_features.workflows import WorkflowsFeature

        feature = WorkflowsFeature()
        feature._component_ref = Mock()
        feature._component_ref.session_id = "test"

        with pytest.raises(ValueError, match="Workflow executor not initialized"):
            await feature._execute_workflow_tool("w1", {})


class TestTop3WorkflowContextInjection:
    """Test that top 3 similar workflows are injected into input."""

    @pytest.fixture
    def mock_neo4j(self):
        """Mock Neo4j component."""
        neo4j = Mock()
        neo4j.init_vector_index = Mock()
        neo4j.run = Mock(return_value=[])
        neo4j.similarity_search = Mock(return_value=[])
        return neo4j

    @pytest.fixture
    def feature(self, mock_neo4j):
        """Create WorkflowsFeature with mocked Neo4j."""
        from woodwork.components.internal_features.workflows import WorkflowsFeature

        feature = WorkflowsFeature()
        feature._neo4j_component = mock_neo4j
        feature._component_ref = Mock()
        feature._component_ref.name = "test_agent"
        feature._component_ref.model = Mock()
        feature._component_ref.model._api_key = "test-key"

        return feature

    def test_inject_top_3_workflows_with_high_similarity(self, feature, mock_neo4j):
        """Test that top 3 workflows with high similarity are injected."""
        from woodwork.types.events import InputReceivedPayload

        # Mock 3 similar workflows
        mock_neo4j.similarity_search.return_value = [
            {"nodeID": "p1", "score": 0.95, "text": "Similar task 1"},
            {"nodeID": "p2", "score": 0.88, "text": "Similar task 2"},
            {"nodeID": "p3", "score": 0.80, "text": "Similar task 3"},
        ]

        # Mock workflow details
        feature._get_workflow_detail = Mock(side_effect=[
            {
                "workflow_id": "w1",
                "name": "Workflow 1",
                "description": "First workflow",
                "actions": [
                    {"tool": "t1", "action": "a1", "inputs": {}, "output": "o1", "sequence": 0}
                ]
            },
            {
                "workflow_id": "w2",
                "name": "Workflow 2",
                "description": "Second workflow",
                "actions": [
                    {"tool": "t2", "action": "a2", "inputs": {}, "output": "o2", "sequence": 0}
                ]
            },
            {
                "workflow_id": "w3",
                "name": "Workflow 3",
                "description": "Third workflow",
                "actions": [
                    {"tool": "t3", "action": "a3", "inputs": {}, "output": "o3", "sequence": 0}
                ]
            },
        ])

        payload = InputReceivedPayload(
            input="Process data files",
            inputs={},
            session_id="test",
            component_id="agent",
            component_type="agent"
        )

        result = feature._check_similar_workflows_pipe(payload)

        # Verify all 3 workflows were injected
        assert "[Available Similar Workflows]:" in result.input
        assert "Workflow 1" in result.input
        assert "Workflow 2" in result.input
        assert "Workflow 3" in result.input
        assert "w1" in result.input
        assert "w2" in result.input
        assert "w3" in result.input

    def test_inject_workflows_includes_similarity_scores(self, feature, mock_neo4j):
        """Test that injected workflows include similarity scores."""
        from woodwork.types.events import InputReceivedPayload

        mock_neo4j.similarity_search.return_value = [
            {"nodeID": "p1", "score": 0.95, "text": "Similar task"},
        ]

        feature._get_workflow_detail = Mock(return_value={
            "workflow_id": "w1",
            "name": "Test Workflow",
            "actions": []
        })

        payload = InputReceivedPayload(
            input="Test input",
            inputs={},
            session_id="test",
            component_id="agent",
            component_type="agent"
        )

        result = feature._check_similar_workflows_pipe(payload)

        # Verify similarity score is shown
        assert "95%" in result.input or "0.95" in result.input

    def test_inject_workflows_shows_action_sequences(self, feature, mock_neo4j):
        """Test that injected workflows show action sequences."""
        from woodwork.types.events import InputReceivedPayload

        mock_neo4j.similarity_search.return_value = [
            {"nodeID": "p1", "score": 0.90, "text": "Similar task"},
        ]

        feature._get_workflow_detail = Mock(return_value={
            "workflow_id": "w1",
            "name": "Data Processing",
            "actions": [
                {
                    "tool": "file_tool",
                    "action": "read",
                    "inputs": {"path": "data.csv"},
                    "output": "file_data",
                    "sequence": 0
                },
                {
                    "tool": "analysis_tool",
                    "action": "analyze",
                    "inputs": {"data": "file_data"},
                    "output": "results",
                    "sequence": 1
                }
            ]
        })

        payload = InputReceivedPayload(
            input="Process data",
            inputs={},
            session_id="test",
            component_id="agent",
            component_type="agent"
        )

        result = feature._check_similar_workflows_pipe(payload)

        # Verify action steps are shown
        assert "file_tool" in result.input
        assert "read" in result.input
        assert "analysis_tool" in result.input
        assert "analyze" in result.input

    def test_inject_workflows_includes_execute_instructions(self, feature, mock_neo4j):
        """Test that injection includes instructions for using execute_workflow."""
        from woodwork.types.events import InputReceivedPayload

        mock_neo4j.similarity_search.return_value = [
            {"nodeID": "p1", "score": 0.90, "text": "Similar"},
        ]

        feature._get_workflow_detail = Mock(return_value={
            "workflow_id": "w1",
            "name": "Test",
            "actions": []
        })

        payload = InputReceivedPayload(
            input="Test",
            inputs={},
            session_id="test",
            component_id="agent",
            component_type="agent"
        )

        result = feature._check_similar_workflows_pipe(payload)

        # Verify instructions are present
        assert "execute_workflow" in result.input
        assert "workflow_id" in result.input or "ID:" in result.input

    def test_no_injection_with_low_similarity(self, feature, mock_neo4j):
        """Test that workflows below threshold are not injected."""
        from woodwork.types.events import InputReceivedPayload

        # Low similarity scores (below 0.75 threshold)
        mock_neo4j.similarity_search.return_value = [
            {"nodeID": "p1", "score": 0.50, "text": "Different task"},
            {"nodeID": "p2", "score": 0.60, "text": "Another task"},
        ]

        payload = InputReceivedPayload(
            input="Test input",
            inputs={},
            session_id="test",
            component_id="agent",
            component_type="agent"
        )

        result = feature._check_similar_workflows_pipe(payload)

        # Should not inject workflows due to low similarity
        assert "[Available Similar Workflows]:" not in result.input

    def test_no_injection_with_no_matches(self, feature, mock_neo4j):
        """Test no injection when no similar workflows found."""
        from woodwork.types.events import InputReceivedPayload

        mock_neo4j.similarity_search.return_value = []

        payload = InputReceivedPayload(
            input="Test input",
            inputs={},
            session_id="test",
            component_id="agent",
            component_type="agent"
        )

        result = feature._check_similar_workflows_pipe(payload)

        assert "[Available Similar Workflows]:" not in result.input
        assert result.input == "Test input"

    def test_format_workflow_contexts_limits_actions(self, feature):
        """Test that _format_workflow_contexts limits actions to 5."""
        contexts = [
            {
                'rank': 1,
                'similarity': 0.95,
                'workflow_id': 'w1',
                'name': 'Long Workflow',
                'description': 'A workflow with many steps',
                'actions': [
                    {'tool': f't{i}', 'action': f'a{i}', 'inputs': {}, 'output': f'o{i}', 'sequence': i}
                    for i in range(10)  # 10 actions
                ]
            }
        ]

        result = feature._format_workflow_contexts(contexts)

        # Should show max 5 actions
        lines = result.split('\n')
        action_lines = [l for l in lines if l.strip().startswith(('1.', '2.', '3.', '4.', '5.', '6.'))]

        # Should have 5 action lines plus "... and X more steps"
        assert '... and 5 more steps' in result

    def test_get_workflow_detail_returns_complete_data(self, feature, mock_neo4j):
        """Test _get_workflow_detail returns complete workflow information."""
        mock_neo4j.run.return_value = [
            {
                'workflow_id': 'w123',
                'name': 'Test Workflow',
                'description': 'A test workflow',
                'prompt': 'Original prompt',
                'actions': [
                    {
                        'tool': 'file_tool',
                        'action': 'read',
                        'inputs': '{"path": "test.txt"}',
                        'output': 'file_data',
                        'sequence': 0
                    }
                ]
            }
        ]

        result = feature._get_workflow_detail("prompt_node_123")

        assert result is not None
        assert result['workflow_id'] == 'w123'
        assert result['name'] == 'Test Workflow'
        assert result['description'] == 'A test workflow'
        assert len(result['actions']) == 1
        assert result['actions'][0]['inputs'] == {"path": "test.txt"}  # Parsed from JSON

    def test_get_workflow_detail_sorts_actions_by_sequence(self, feature, mock_neo4j):
        """Test _get_workflow_detail sorts actions by sequence number."""
        mock_neo4j.run.return_value = [
            {
                'workflow_id': 'w1',
                'name': 'Test',
                'actions': [
                    {'tool': 't2', 'action': 'a2', 'inputs': '{}', 'output': 'o2', 'sequence': 2},
                    {'tool': 't1', 'action': 'a1', 'inputs': '{}', 'output': 'o1', 'sequence': 1},
                    {'tool': 't0', 'action': 'a0', 'inputs': '{}', 'output': 'o0', 'sequence': 0},
                ]
            }
        ]

        result = feature._get_workflow_detail("prompt_node")

        # Actions should be sorted by sequence
        assert result['actions'][0]['sequence'] == 0
        assert result['actions'][1]['sequence'] == 1
        assert result['actions'][2]['sequence'] == 2
