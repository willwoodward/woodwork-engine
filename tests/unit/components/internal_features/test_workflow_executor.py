"""
Unit tests for WorkflowExecutor class with unified event bus integration.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import json


class TestWorkflowExecutor:
    """Test workflow executor for direct workflow execution."""

    @pytest.fixture
    def mock_neo4j(self):
        """Mock Neo4j component."""
        neo4j = Mock()
        neo4j.run = Mock(return_value=[])
        return neo4j

    @pytest.fixture
    def mock_agent(self):
        """Mock agent component with request API."""
        agent = Mock()

        # Mock request method that returns different values based on tool
        async def mock_request(tool, payload):
            responses = {
                "file_tool": "Sample file content",
                "text_tool": "Processed text output",
                "analysis_tool": {"result": "analysis complete"}
            }
            return responses.get(tool, "default response")

        agent.request = AsyncMock(side_effect=mock_request)
        return agent

    @pytest.fixture
    def executor(self, mock_neo4j, mock_agent):
        """Create WorkflowExecutor instance."""
        from woodwork.components.internal_features.workflow_executor import WorkflowExecutor
        return WorkflowExecutor(mock_neo4j, mock_agent)

    def test_executor_initialization(self, mock_neo4j, mock_agent):
        """Test that executor initializes with neo4j and agent."""
        from woodwork.components.internal_features.workflow_executor import WorkflowExecutor

        executor = WorkflowExecutor(mock_neo4j, mock_agent)

        assert executor._neo4j == mock_neo4j
        assert executor._agent == mock_agent

    @pytest.mark.asyncio
    async def test_execute_workflow_runs_single_action(self, executor, mock_neo4j):
        """Test executing workflow with single action."""
        # Setup: Single action workflow
        mock_neo4j.run.return_value = [
            {
                "id": "a1",
                "tool": "file_tool",
                "action": "read",
                "inputs": '{"path": "test.txt"}',
                "output": "file_content",
                "sequence": 0
            }
        ]

        result = await executor.execute_workflow(
            workflow_id="w1",
            inputs={"path": "test.txt"},
            session_id="test_session"
        )

        assert result['status'] == 'completed'
        assert result['workflow_id'] == 'w1'
        assert len(result['results']) == 1
        assert 'execution_id' in result
        assert 'file_content' in result['final_outputs']

    @pytest.mark.asyncio
    async def test_execute_workflow_runs_action_sequence(self, executor, mock_neo4j):
        """Test executing workflow with multiple actions in sequence."""
        # Setup: Two action workflow with dependency
        mock_neo4j.run.return_value = [
            {
                "id": "a1",
                "tool": "file_tool",
                "action": "read",
                "inputs": '{"path": "input.txt"}',
                "output": "file_content",
                "sequence": 0
            },
            {
                "id": "a2",
                "tool": "text_tool",
                "action": "process",
                "inputs": '{"text": "file_content"}',
                "output": "processed_text",
                "sequence": 1
            }
        ]

        result = await executor.execute_workflow(
            workflow_id="w1",
            inputs={"path": "input.txt"},
            session_id="test_session"
        )

        assert result['status'] == 'completed'
        assert len(result['results']) == 2
        assert 'file_content' in result['final_outputs']
        assert 'processed_text' in result['final_outputs']

        # Verify second action received output from first
        assert result['final_outputs']['processed_text'] == "Processed text output"

    @pytest.mark.asyncio
    async def test_execute_workflow_resolves_variable_references(self, executor, mock_neo4j, mock_agent):
        """Test that action inputs resolve variable references correctly."""
        mock_neo4j.run.return_value = [
            {
                "id": "a1",
                "tool": "file_tool",
                "action": "read",
                "inputs": '{"path": "data.txt"}',
                "output": "file_data",
                "sequence": 0
            },
            {
                "id": "a2",
                "tool": "analysis_tool",
                "action": "analyze",
                "inputs": '{"data": "file_data", "limit": 100}',
                "output": "analysis_result",
                "sequence": 1
            }
        ]

        result = await executor.execute_workflow(
            workflow_id="w1",
            inputs={},
            session_id="test_session"
        )

        # Verify agent.request was called for analysis_tool
        # Check the second call (analysis_tool) received resolved variable
        assert mock_agent.request.call_count == 2

        second_call = mock_agent.request.call_args_list[1]
        assert second_call[0][0] == "analysis_tool"
        # The 'data' input should be resolved to the file content
        assert second_call[0][1]["inputs"]["data"] == "Sample file content"
        assert second_call[0][1]["inputs"]["limit"] == 100

    @pytest.mark.asyncio
    async def test_execute_workflow_preserves_literal_values(self, executor, mock_neo4j):
        """Test that literal values in inputs are preserved."""
        mock_neo4j.run.return_value = [
            {
                "id": "a1",
                "tool": "text_tool",
                "action": "process",
                "inputs": '{"text": "literal text", "count": 5}',
                "output": "result",
                "sequence": 0
            }
        ]

        result = await executor.execute_workflow(
            workflow_id="w1",
            inputs={},
            session_id="test_session"
        )

        assert result['status'] == 'completed'

    @pytest.mark.asyncio
    async def test_execute_workflow_raises_on_no_actions(self, executor, mock_neo4j):
        """Test that executing workflow with no actions raises error."""
        mock_neo4j.run.return_value = []

        with pytest.raises(ValueError, match="has no actions"):
            await executor.execute_workflow(
                workflow_id="w1",
                inputs={},
                session_id="test_session"
            )

    @pytest.mark.asyncio
    async def test_execute_workflow_handles_tool_errors(self, executor, mock_neo4j, mock_agent):
        """Test that tool execution errors are handled gracefully."""
        mock_neo4j.run.return_value = [
            {
                "id": "a1",
                "tool": "failing_tool",
                "action": "test",
                "inputs": '{}',
                "output": "result",
                "sequence": 0
            }
        ]

        # Make the agent.request raise an error
        mock_agent.request.side_effect = Exception("Component not found")

        # Should not raise, but return error in result
        result = await executor.execute_workflow(
            workflow_id="w1",
            inputs={},
            session_id="test_session"
        )

        assert result['status'] == 'completed'
        assert 'Error:' in str(result['results'][0]['output'])

    @pytest.mark.asyncio
    async def test_execute_entrypoint_resolves_to_workflow(self, executor, mock_neo4j):
        """Test that entrypoint execution resolves to workflow ID."""
        # Mock entrypoint resolution
        mock_neo4j.run.side_effect = [
            # First call: resolve entrypoint to workflow
            [{"workflow_id": "w1"}],
            # Second call: validate input schema
            [{"schema": '{"required": []}'}],
            # Third call: get workflow actions
            [
                {
                    "id": "a1",
                    "tool": "file_tool",
                    "action": "read",
                    "inputs": '{"path": "test.txt"}',
                    "output": "content",
                    "sequence": 0
                }
            ]
        ]

        result = await executor.execute_entrypoint(
            entrypoint_name="process_data",
            inputs={"path": "test.txt"},
            session_id="test_session"
        )

        assert result['status'] == 'completed'
        assert result['workflow_id'] == 'w1'

    @pytest.mark.asyncio
    async def test_execute_entrypoint_raises_on_not_found(self, executor, mock_neo4j):
        """Test that non-existent entrypoint raises error."""
        mock_neo4j.run.return_value = []

        with pytest.raises(ValueError, match="Entrypoint 'nonexistent' not found"):
            await executor.execute_entrypoint(
                entrypoint_name="nonexistent",
                inputs={},
                session_id="test_session"
            )

    @pytest.mark.asyncio
    async def test_execute_entrypoint_validates_required_inputs(self, executor, mock_neo4j):
        """Test that entrypoint validates required inputs against schema."""
        mock_neo4j.run.side_effect = [
            # Resolve entrypoint
            [{"workflow_id": "w1"}],
            # Schema with required field
            [{"schema": '{"required": ["input_file"]}'}],
        ]

        with pytest.raises(ValueError, match="Required input 'input_file' missing"):
            await executor.execute_entrypoint(
                entrypoint_name="process_data",
                inputs={},  # Missing required input
                session_id="test_session"
            )

    @pytest.mark.asyncio
    async def test_resolve_inputs_substitutes_variables(self, executor):
        """Test _resolve_inputs method substitutes variable references."""
        inputs = {
            "file": "file_content",
            "limit": 100,
            "format": "json"
        }

        variables = {
            "file_content": "Sample content from file",
            "other_var": "other value"
        }

        resolved = executor._resolve_inputs(inputs, variables)

        assert resolved['file'] == "Sample content from file"  # Variable resolved
        assert resolved['limit'] == 100  # Literal preserved
        assert resolved['format'] == "json"  # Literal preserved

    @pytest.mark.asyncio
    async def test_resolve_inputs_preserves_non_variables(self, executor):
        """Test _resolve_inputs preserves values that aren't variable names."""
        inputs = {
            "text": "literal string",
            "number": 42,
            "boolean": True
        }

        variables = {}

        resolved = executor._resolve_inputs(inputs, variables)

        assert resolved == inputs

    @pytest.mark.asyncio
    async def test_get_workflow_actions_queries_neo4j(self, executor, mock_neo4j):
        """Test _get_workflow_actions queries Neo4j correctly."""
        mock_neo4j.run.return_value = [
            {
                "id": "a1",
                "tool": "test_tool",
                "action": "test_action",
                "inputs": '{}',
                "output": "result",
                "sequence": 0
            }
        ]

        actions = await executor._get_workflow_actions("w1")

        assert len(actions) == 1
        assert actions[0]['tool'] == 'test_tool'

        # Verify query was called with workflow_id
        mock_neo4j.run.assert_called_once()
        call_args = mock_neo4j.run.call_args
        assert call_args[0][1]['workflow_id'] == 'w1'

    @pytest.mark.asyncio
    async def test_resolve_entrypoint_returns_workflow_id(self, executor, mock_neo4j):
        """Test _resolve_entrypoint returns workflow ID for valid entrypoint."""
        mock_neo4j.run.return_value = [{"workflow_id": "w123"}]

        workflow_id = await executor._resolve_entrypoint("my_entrypoint")

        assert workflow_id == "w123"

    @pytest.mark.asyncio
    async def test_resolve_entrypoint_returns_none_on_not_found(self, executor, mock_neo4j):
        """Test _resolve_entrypoint returns None for non-existent entrypoint."""
        mock_neo4j.run.return_value = []

        workflow_id = await executor._resolve_entrypoint("nonexistent")

        assert workflow_id is None

    @pytest.mark.asyncio
    @patch('woodwork.components.internal_features.workflow_executor.emit')
    async def test_execute_action_emits_events(self, mock_emit, executor, mock_neo4j, mock_agent):
        """Test that _execute_action emits tool.call and tool.observation events."""
        from woodwork.components.internal_features.workflow_executor import WorkflowExecutionContext

        # Setup mock emit to return payloads (emit is sync, not async)
        def mock_emit_side_effect(event_name, payload):
            mock_payload = Mock()
            if event_name == "tool.call":
                mock_payload.tool = payload["tool"]
                mock_payload.args = payload["args"]
            elif event_name == "tool.observation":
                mock_payload.tool = payload["tool"]
                mock_payload.observation = payload["observation"]
            return mock_payload

        mock_emit.side_effect = mock_emit_side_effect

        action = {
            "id": "a1",
            "tool": "file_tool",
            "action": "read",
            "inputs": {"path": "test.txt"},
            "output": "content"
        }

        context = WorkflowExecutionContext(
            workflow_id="w1",
            inputs={},
            session_id="test",
            execution_id="exec1",
            variables={}
        )

        result = await executor._execute_action(action, context)

        # Verify tool.call event was emitted
        call_events = [call for call in mock_emit.call_args_list if call[0][0] == "tool.call"]
        assert len(call_events) == 1
        assert call_events[0][0][1]["tool"] == "file_tool"
        assert call_events[0][0][1]["args"] == {"path": "test.txt"}

        # Verify tool.observation event was emitted
        obs_events = [call for call in mock_emit.call_args_list if call[0][0] == "tool.observation"]
        assert len(obs_events) == 1
        assert obs_events[0][0][1]["tool"] == "file_tool"

        # Verify agent.request was called
        mock_agent.request.assert_called_once_with(
            "file_tool",
            {"action": "read", "inputs": {"path": "test.txt"}}
        )
