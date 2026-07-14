"""Tests for woodwork.core.types."""

from woodwork.core.types import AgentContext, Message, Step


def test_message_fields():
    m = Message(role="user", content="hello")
    assert m.role == "user"
    assert m.content == "hello"


def test_step_defaults():
    s = Step(thought="thinking")
    assert s.tool is None
    assert s.action is None
    assert s.inputs == {}
    assert s.observation is None
    assert s.output_var is None


def test_agent_context_defaults():
    ctx = AgentContext(query="do something", session_id="s1")
    assert ctx.inputs == {}
    assert ctx.history == []
    assert ctx.steps == []
    assert ctx.variables == {}


def test_agent_context_with_data():
    ctx = AgentContext(
        query="q",
        session_id="s",
        inputs={"k": "v"},
        history=[Message("user", "hi")],
    )
    assert ctx.inputs["k"] == "v"
    assert len(ctx.history) == 1
