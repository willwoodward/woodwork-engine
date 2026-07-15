"""Tests for woodwork.api_events (Event constants)."""

from woodwork.api_events import Event


class TestEventConstants:
    def test_agent_tool_call(self):
        assert Event.Agent.TOOL_CALL == "tool.call"

    def test_agent_thought(self):
        assert Event.Agent.THOUGHT == "agent.thought"

    def test_agent_action(self):
        assert Event.Agent.ACTION == "agent.action"

    def test_agent_step_complete(self):
        assert Event.Agent.STEP_COMPLETE == "agent.step_complete"

    def test_component_events_inherited_by_agent(self):
        assert Event.Agent.STARTED == "component.started"
        assert Event.Agent.STOPPED == "component.stopped"
        assert Event.Agent.ERROR == "component.error"

    def test_mcp_inherits_component_events(self):
        assert Event.MCP.STARTED == "component.started"

    def test_input_received(self):
        assert Event.Input.RECEIVED == "input.received"

    def test_llm_inherits_component_events(self):
        assert Event.LLM.STARTED == "component.started"
