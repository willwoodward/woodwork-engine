"""
Unit tests for WorkflowExecutor class.

Following TDD - these tests are written BEFORE implementation.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
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
    def mock_task_master(self):
        """Mock task master with tools."""
        task_master = Mock()

        # Mock file tool
        file_tool = Mock()
        file_tool.execute = AsyncMock(return_value="Sample file content")

        # Mock text tool
        text_tool = Mock()
        text_tool.execute = AsyncMock(return_value="Processed text output")

        # Mock analysis tool
        analysis_tool = Mock()
        analysis_tool.execute = AsyncMock(return_value={"result": "analysis complete"})

        task_master.get_tool = Mock(side_effect=lambda name: {
            "file_tool": file_tool,
            "text_tool": text_tool,
            "analysis_tool": analysis_tool
        }.get(name))

        return task_master

    @pytest.fixture
    def executor(self, mock_neo4j, mock_task_master):
        """Create WorkflowExecutor instance."""
        from woodwork.components.internal_features.workflow_executor import WorkflowExecutor
        return WorkflowExecutor(mock_neo4j, mock_task_master)

    def test_executor_initialization(self, mock_neo4j, mock_task_master):
        """Test that executor initializes with neo4j and task_master."""
        from woodwork.components.internal_features.workflow_executor import WorkflowExecutor

        executor = WorkflowExecutor(mock_neo4j, mock_task_master)

        assert executor._neo4j == mock_neo4j
        assert executor._task_master == mock_task_master

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
    async def test_execute_workflow_resolves_variable_references(self, executor, mock_neo4j, mock_task_master):
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

        # Verify analysis tool received resolved variable
        analysis_tool = mock_task_master.get_tool("analysis_tool")

        # Check that execute was called with resolved inputs
        call_args = analysis_tool.execute.call_args
        assert call_args is not None

        # The 'data' input should be resolved to the file content
        assert "Sample file content" in str(call_args)

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
    async def test_execute_workflow_raises_on_missing_tool(self, executor, mock_neo4j, mock_task_master):
        """Test that missing tool raises error."""
        mock_neo4j.run.return_value = [
            {
                "id": "a1",
                "tool": "nonexistent_tool",
                "action": "test",
                "inputs": '{}',
                "output": "result",
                "sequence": 0
            }
        ]

        mock_task_master.get_tool.return_value = None

        with pytest.raises(ValueError, match="Tool 'nonexistent_tool' not found"):
            await executor.execute_workflow(
                workflow_id="w1",
                inputs={},
                session_id="test_session"
            )

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
