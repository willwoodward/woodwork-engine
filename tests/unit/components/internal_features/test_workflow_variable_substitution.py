"""
Tests for workflow variable substitution across actions.

This ensures that output variables from one action can be used as inputs to another.
"""

import pytest
from unittest.mock import Mock, AsyncMock
import json


class TestWorkflowVariableSubstitution:
    """Test variable substitution in workflow execution."""

    @pytest.fixture
    def mock_neo4j(self):
        """Mock Neo4j with multi-action workflow."""
        neo4j = Mock()

        # Workflow with 3 actions where each uses previous output
        neo4j.run.return_value = [
            {
                "id": "a1",
                "tool": "file_tool",
                "action": "read",
                "inputs": '{"path": "data.txt"}',
                "output": "file_contents",
                "sequence": 0
            },
            {
                "id": "a2",
                "tool": "text_tool",
                "action": "process",
                "inputs": '{"text": "file_contents"}',  # Uses output from a1
                "output": "processed_data",
                "sequence": 1
            },
            {
                "id": "a3",
                "tool": "save_tool",
                "action": "save",
                "inputs": '{"data": "processed_data", "format": "json"}',  # Uses output from a2
                "output": "saved_file",
                "sequence": 2
            }
        ]

        return neo4j

    @pytest.fixture
    def mock_task_master(self):
        """Mock task master with tools."""
        task_master = Mock()

        # Track tool results for variable substitution
        tool_results = {
            "file_tool": "Sample file content from data.txt",
            "text_tool": "Processed: Sample file content from data.txt",
            "save_tool": "/output/result.json"
        }

        # Mock the request method that WorkflowExecutor actually uses
        async def mock_request(tool_name, params):
            return tool_results.get(tool_name)

        task_master.request = AsyncMock(side_effect=mock_request)

        # Keep get_tool for backward compatibility
        file_tool = Mock()
        file_tool.execute = AsyncMock(return_value=tool_results["file_tool"])

        text_tool = Mock()
        text_tool.execute = AsyncMock(return_value=tool_results["text_tool"])

        save_tool = Mock()
        save_tool.execute = AsyncMock(return_value=tool_results["save_tool"])

        task_master.get_tool = Mock(side_effect=lambda name: {
            "file_tool": file_tool,
            "text_tool": text_tool,
            "save_tool": save_tool
        }.get(name))

        return task_master

    @pytest.fixture
    def executor(self, mock_neo4j, mock_task_master):
        """Create WorkflowExecutor."""
        from woodwork.components.internal_features.workflow_executor import WorkflowExecutor
        return WorkflowExecutor(mock_neo4j, mock_task_master)

    @pytest.mark.asyncio
    async def test_variable_substitution_across_actions(self, executor, mock_task_master):
        """Test that variables are substituted correctly across multiple actions."""
        result = await executor.execute_workflow(
            workflow_id="w1",
            inputs={},
            session_id="test"
        )

        assert result['status'] == 'completed'
        assert len(result['results']) == 3

        # Verify each tool was called with the correct resolved inputs via request()
        request_calls = mock_task_master.request.call_args_list

        # First tool called with literal input
        file_call = request_calls[0]
        assert file_call[0][0] == "file_tool"  # tool name
        assert file_call[0][1]['inputs']['path'] == 'data.txt'

        # Second tool called with resolved variable (output from first)
        text_call = request_calls[1]
        assert text_call[0][0] == "text_tool"
        assert text_call[0][1]['inputs']['text'] == "Sample file content from data.txt"  # Resolved!

        # Third tool called with resolved variable (output from second)
        save_call = request_calls[2]
        assert save_call[0][0] == "save_tool"
        assert save_call[0][1]['inputs']['data'] == "Processed: Sample file content from data.txt"  # Resolved!
        assert save_call[0][1]['inputs']['format'] == 'json'  # Literal preserved

    @pytest.mark.asyncio
    async def test_workflow_context_accumulates_variables(self, executor):
        """Test that workflow context accumulates all output variables."""
        result = await executor.execute_workflow(
            workflow_id="w1",
            inputs={"initial_input": "test_value"},
            session_id="test"
        )

        # Check that all output variables are in final_outputs
        assert 'file_contents' in result['final_outputs']
        assert 'processed_data' in result['final_outputs']
        assert 'saved_file' in result['final_outputs']

        # Check that initial inputs are preserved
        assert 'initial_input' in result['final_outputs']
        assert result['final_outputs']['initial_input'] == 'test_value'

    @pytest.mark.asyncio
    async def test_resolve_inputs_method(self, executor):
        """Test _resolve_inputs method directly."""
        inputs = {
            "file": "file_contents",
            "format": "json",
            "count": 5
        }

        variables = {
            "file_contents": "actual_content.txt",
            "other_var": "other_value"
        }

        resolved = executor._resolve_inputs(inputs, variables)

        # Variable reference should be resolved
        assert resolved['file'] == "actual_content.txt"

        # Literals should be preserved
        assert resolved['format'] == "json"
        assert resolved['count'] == 5

    @pytest.mark.asyncio
    async def test_non_existent_variable_treated_as_literal(self, executor):
        """Test that non-existent variable names are treated as literals."""
        inputs = {
            "some_key": "non_existent_variable"
        }

        variables = {
            "actual_var": "actual_value"
        }

        resolved = executor._resolve_inputs(inputs, variables)

        # Since "non_existent_variable" is not in variables, treat as literal
        assert resolved['some_key'] == "non_existent_variable"


class TestWorkflowCaptureWithVariables:
    """Test that workflow capture tracks variable dependencies."""

    @pytest.fixture
    def feature(self):
        """Create WorkflowsFeature."""
        from woodwork.components.internal_features.workflows import WorkflowsFeature
        return WorkflowsFeature()

    @pytest.fixture
    def mock_neo4j(self):
        """Mock Neo4j component."""
        neo4j = Mock()
        neo4j.run = Mock(return_value=[])
        return neo4j

    @pytest.fixture
    def mock_task_master_simple(self):
        """Mock task master for mixed inputs test."""
        task_master = Mock()
        tool1 = Mock()
        tool1.execute = AsyncMock(return_value="output1")
        tool2 = Mock()
        tool2.execute = AsyncMock(return_value="output2")
        task_master.get_tool = Mock(side_effect=lambda name: {
            "tool1": tool1,
            "tool2": tool2
        }.get(name))
        return task_master

    def test_action_dependency_detection(self, feature, mock_neo4j):
        """Test that _create_action_relationships detects variable dependencies."""
        from woodwork.types.events import AgentActionPayload

        feature._neo4j_component = mock_neo4j
        feature._current_workflow_id = "w1"
        feature._component_ref = Mock()
        feature._component_ref.name = "test"
        feature._component_ref.model = Mock()
        feature._component_ref.model._api_key = "key"

        # Simulate first action
        action1_data = {
            "tool": "file_tool",
            "action": "read",
            "inputs": {},
            "output": "file_data"
        }

        payload1 = AgentActionPayload(
            action=json.dumps(action1_data),
            component_id="test",
            component_type="agent"
        )

        feature._sync_action_hook(payload1)

        # Simulate second action that depends on first
        action2_data = {
            "tool": "process_tool",
            "action": "process",
            "inputs": {"data": "file_data"},  # References output from action1
            "output": "result"
        }

        payload2 = AgentActionPayload(
            action=json.dumps(action2_data),
            component_id="test",
            component_type="agent"
        )

        feature._sync_action_hook(payload2)

        # Check that DEPENDS_ON relationship was created
        calls = [str(call) for call in mock_neo4j.run.call_args_list]
        depends_on_calls = [c for c in calls if 'DEPENDS_ON' in c]

        assert len(depends_on_calls) > 0, "Should have created DEPENDS_ON relationship"

    def test_sequential_actions_get_next_relationship(self, feature, mock_neo4j):
        """Test that sequential actions get NEXT relationships."""
        from woodwork.types.events import AgentActionPayload

        feature._neo4j_component = mock_neo4j
        feature._current_workflow_id = "w1"
        feature._component_ref = Mock()
        feature._component_ref.name = "test"
        feature._component_ref.model = Mock()
        feature._component_ref.model._api_key = "key"

        # Add two sequential actions without variable dependencies
        for i in range(2):
            action_data = {
                "tool": f"tool{i}",
                "action": f"action{i}",
                "inputs": {},
                "output": f"out{i}"
            }

            payload = AgentActionPayload(
                action=json.dumps(action_data),
                component_id="test",
                component_type="agent"
            )

            feature._sync_action_hook(payload)

        # Check that NEXT relationship was created
        calls = [str(call) for call in mock_neo4j.run.call_args_list]
        next_calls = [c for c in calls if 'NEXT' in c]

        assert len(next_calls) > 0, "Should have created NEXT relationship for sequential actions"

    def test_first_action_gets_starts_relationship(self, feature, mock_neo4j):
        """Test that first action gets STARTS relationship from Prompt."""
        from woodwork.types.events import AgentActionPayload

        feature._neo4j_component = mock_neo4j
        feature._current_workflow_id = "w1"
        feature._component_ref = Mock()
        feature._component_ref.name = "test"
        feature._component_ref.model = Mock()
        feature._component_ref.model._api_key = "key"

        # Add first action
        action_data = {
            "tool": "tool1",
            "action": "action1",
            "inputs": {},
            "output": "out1"
        }

        payload = AgentActionPayload(
            action=json.dumps(action_data),
            component_id="test",
            component_type="agent"
        )

        feature._sync_action_hook(payload)

        # Check that STARTS relationship was created
        calls = [str(call) for call in mock_neo4j.run.call_args_list]
        starts_calls = [c for c in calls if 'STARTS' in c]

        assert len(starts_calls) > 0, "First action should have STARTS relationship from Prompt"
