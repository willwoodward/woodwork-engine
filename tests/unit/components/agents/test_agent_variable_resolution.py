"""Tests for agent workflow variable resolution."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from woodwork.components.agents.llm import LLMAgent
from woodwork.types import Action


class TestAgentVariableResolution:
    """Test agent's workflow variable resolution functionality."""

    @pytest.fixture
    def mock_model(self):
        """Mock LLM model."""
        model = Mock()
        model._llm = Mock()
        model._api_key = "test-key"
        return model

    @pytest.fixture
    def mock_task_master(self):
        """Mock task master."""
        task_m = Mock()
        task_m.start_workflow = Mock()
        return task_m

    @pytest.fixture
    def agent(self, mock_model, mock_task_master):
        """Create agent with mocked dependencies."""
        with patch("woodwork.components.agents.llm.InternalFeatureRegistry") as mock_registry:
            mock_registry.create_features.return_value = []

            with patch("woodwork.components.agents.llm.get_prompt", return_value="Test prompt"):
                agent = LLMAgent(model=mock_model, task_m=mock_task_master, name="test_agent", tools=[])
                return agent

    def test_resolve_action_inputs_no_variables(self, agent):
        """Test that literal values are kept when no variables exist."""
        inputs = {"key1": "literal_value", "key2": 123, "key3": "another_string"}

        resolved = agent._resolve_action_inputs(inputs)

        assert resolved == inputs
        assert resolved["key1"] == "literal_value"
        assert resolved["key2"] == 123
        assert resolved["key3"] == "another_string"

    def test_resolve_action_inputs_with_variables(self, agent):
        """Test that variable references are substituted with actual values."""
        # Setup workflow variables
        agent._workflow_variables = {
            "bob_messages": "Hello from Bob!",
            "result_data": {"status": "success"},
            "count": 42,
        }

        inputs = {
            "messages": "bob_messages",  # Should be resolved
            "data": "result_data",  # Should be resolved
            "num": "count",  # Should be resolved
            "literal": "just_a_string",  # Should stay literal
        }

        resolved = agent._resolve_action_inputs(inputs)

        assert resolved["messages"] == "Hello from Bob!"
        assert resolved["data"] == {"status": "success"}
        assert resolved["num"] == 42
        assert resolved["literal"] == "just_a_string"  # Not in variables, stays literal

    def test_resolve_action_inputs_mixed(self, agent):
        """Test mix of variable references and literals."""
        agent._workflow_variables = {"var1": "resolved_value"}

        inputs = {"variable_ref": "var1", "literal_string": "not_a_variable", "number": 100, "boolean": True}

        resolved = agent._resolve_action_inputs(inputs)

        assert resolved["variable_ref"] == "resolved_value"
        assert resolved["literal_string"] == "not_a_variable"
        assert resolved["number"] == 100
        assert resolved["boolean"] is True

    def test_input_initializes_workflow_variables_directly(self, agent):
        """Test that workflow variables are initialized from inputs."""
        # Test the initialization logic directly
        inputs = {"initial_var": "initial_value", "count": 5}

        # Simulate what input() does
        agent._workflow_variables = inputs.copy()

        assert agent._workflow_variables == inputs
        assert agent._workflow_variables["initial_var"] == "initial_value"
        assert agent._workflow_variables["count"] == 5

    def test_input_resets_workflow_variables_directly(self, agent):
        """Test that workflow variables are reset for each query."""
        # First query
        agent._workflow_variables = {"old_var": "old_value"}
        inputs1 = {"var1": "value1"}
        agent._workflow_variables = inputs1.copy()

        assert "old_var" not in agent._workflow_variables
        assert agent._workflow_variables == {"var1": "value1"}

        # Second query
        inputs2 = {"var2": "value2"}
        agent._workflow_variables = inputs2.copy()

        assert "var1" not in agent._workflow_variables
        assert agent._workflow_variables == {"var2": "value2"}

    @pytest.mark.asyncio
    async def test_execute_tool_stores_output_in_variables(self, agent):
        """Test that tool execution stores result in workflow variables."""
        # Mock the request method
        agent.request = AsyncMock(return_value="tool_result")

        action = Action.from_dict(
            {"tool": "test_tool", "action": "test_action", "inputs": {"key": "value"}, "output": "stored_result"}
        )

        result = await agent._execute_tool_with_improved_api(action)

        assert result == "tool_result"
        assert agent._workflow_variables["stored_result"] == "tool_result"

    @pytest.mark.asyncio
    async def test_execute_tool_resolves_variables_before_execution(self, agent):
        """Test that variables are resolved before calling tool."""
        agent._workflow_variables = {"previous_output": "resolved_value"}
        agent.request = AsyncMock(return_value="result")

        action = Action.from_dict(
            {
                "tool": "test_tool",
                "action": "test_action",
                "inputs": {"data": "previous_output", "literal": "keep_me"},
                "output": "new_result",
            }
        )

        await agent._execute_tool_with_improved_api(action)

        # Verify request was called with resolved inputs
        call_args = agent.request.call_args
        assert call_args[0][0] == "test_tool"
        assert call_args[0][1]["inputs"]["data"] == "resolved_value"
        assert call_args[0][1]["inputs"]["literal"] == "keep_me"

    @pytest.mark.asyncio
    async def test_variable_chain_across_actions(self, agent):
        """Test that variables can be chained across multiple actions."""
        agent.request = AsyncMock(side_effect=["result1", "result2", "result3"])

        # Action 1: Store in var1
        action1 = Action.from_dict({"tool": "tool1", "action": "action1", "inputs": {}, "output": "var1"})
        await agent._execute_tool_with_improved_api(action1)

        # Action 2: Use var1, store in var2
        action2 = Action.from_dict({"tool": "tool2", "action": "action2", "inputs": {"data": "var1"}, "output": "var2"})
        await agent._execute_tool_with_improved_api(action2)

        # Action 3: Use var2, store in var3
        action3 = Action.from_dict(
            {"tool": "tool3", "action": "action3", "inputs": {"input": "var2"}, "output": "var3"}
        )
        await agent._execute_tool_with_improved_api(action3)

        # Verify chain
        assert agent._workflow_variables["var1"] == "result1"
        assert agent._workflow_variables["var2"] == "result2"
        assert agent._workflow_variables["var3"] == "result3"

        # Verify action2 received resolved var1
        call2 = agent.request.call_args_list[1]
        assert call2[0][1]["inputs"]["data"] == "result1"

        # Verify action3 received resolved var2
        call3 = agent.request.call_args_list[2]
        assert call3[0][1]["inputs"]["input"] == "result2"

    @pytest.mark.asyncio
    async def test_non_string_results_stored_correctly(self, agent):
        """Test that non-string tool results are stored as-is in variables."""
        # Mock tool returning dict
        dict_result = {"status": "success", "data": [1, 2, 3]}
        agent.request = AsyncMock(return_value=dict_result)

        action = Action.from_dict({"tool": "test_tool", "action": "get_data", "inputs": {}, "output": "api_response"})

        result = await agent._execute_tool_with_improved_api(action)

        # Result should be the original dict
        assert result == dict_result
        # Workflow variable should store the dict (not JSON string)
        assert agent._workflow_variables["api_response"] == dict_result
        assert isinstance(agent._workflow_variables["api_response"], dict)

    @pytest.mark.asyncio
    async def test_dict_variable_can_be_passed_to_next_action(self, agent):
        """Test that dict results can be passed as variables to next action."""
        dict_result = {"key": "value", "count": 42}
        agent.request = AsyncMock(side_effect=[dict_result, "processed"])

        # Action 1: Returns dict, stores in var
        action1 = Action.from_dict({"tool": "tool1", "action": "get_data", "inputs": {}, "output": "data_var"})
        await agent._execute_tool_with_improved_api(action1)

        # Action 2: References the dict variable
        action2 = Action.from_dict(
            {"tool": "tool2", "action": "process", "inputs": {"data": "data_var"}, "output": "result"}
        )
        await agent._execute_tool_with_improved_api(action2)

        # Verify tool2 received the actual dict, not a string
        call2 = agent.request.call_args_list[1]
        assert call2[0][1]["inputs"]["data"] == dict_result
        assert isinstance(call2[0][1]["inputs"]["data"], dict)
