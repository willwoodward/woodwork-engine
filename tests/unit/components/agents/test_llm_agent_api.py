"""Tests for LLMAgent Python API additions: send(), hook(), pipe(), prompt loading."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from woodwork.primitives import File


def _make_model(name="model"):
    """Minimal mock LLM component."""
    m = MagicMock()
    m.name = name
    m.component = "llm"
    m.type = "openai"
    m._api_key = "test-key"
    return m


def _make_agent(prompt=None, model=None, extra=None):
    """Construct an LLMAgent with mocked internals."""
    from woodwork.components.agents.llm import LLMAgent

    model = model or _make_model()

    kwargs = {"name": "agent", "tools": [], "prompt": prompt}
    if extra:
        kwargs.update(extra)

    with (
        patch("woodwork.components.agents.llm.InternalFeatureRegistry"),
        patch("woodwork.components.agents.llm.InternalComponentManager"),
    ):
        return LLMAgent(model=model, **kwargs)


class TestSend:
    @pytest.mark.asyncio
    async def test_send_delegates_to_execute(self):
        agent = _make_agent()
        agent.execute = AsyncMock(return_value="answer")

        result = await agent.send("What is 2+2?")

        agent.execute.assert_called_once_with("run", {"query": "What is 2+2?", "session_id": "default"})
        assert result == "answer"

    @pytest.mark.asyncio
    async def test_send_custom_session_id(self):
        agent = _make_agent()
        agent.execute = AsyncMock(return_value="ok")

        await agent.send("hello", session_id="session-42")

        agent.execute.assert_called_once_with("run", {"query": "hello", "session_id": "session-42"})


class TestHookPipeDecorators:
    def test_hook_registers_on_event_bus(self):
        agent = _make_agent()

        @agent.hook("tool.call")
        def on_tool(payload):
            pass

        assert on_tool in agent.event_bus._hooks["tool.call"]

    def test_hook_returns_function_unchanged(self):
        agent = _make_agent()

        @agent.hook("tool.call")
        def on_tool(payload):
            return "x"

        assert on_tool("y") == "x"

    def test_pipe_registers_on_event_bus(self):
        agent = _make_agent()

        @agent.pipe("agent.action")
        def transform(payload):
            return payload

        assert transform in agent.event_bus._pipes["agent.action"]

    def test_hook_with_event_constant(self):
        from woodwork.api_events import Event

        agent = _make_agent()

        @agent.hook(Event.Agent.TOOL_CALL)
        def fn(p):
            pass

        assert fn in agent.event_bus._hooks["tool.call"]


class TestPromptLoading:
    def test_file_prompt_appended_onto_default(self, tmp_path):
        prompt_file = tmp_path / "system.txt"
        prompt_file.write_text("You are helpful.")

        agent = _make_agent(prompt=File(str(prompt_file)))
        # Custom text must appear in the final prompt
        assert "You are helpful." in agent._prompt

    def test_file_prompt_missing_falls_back_to_default(self, tmp_path):
        missing = File(str(tmp_path / "nonexistent.txt"))
        agent = _make_agent(prompt=missing)
        # Falls back gracefully — either empty string or the default ReAct prompt
        assert isinstance(agent._prompt, str)

    def test_inline_str_prompt_appended_onto_default(self):
        agent = _make_agent(prompt="Be concise.")
        assert "Be concise." in agent._prompt

    def test_no_prompt_uses_default(self):
        agent = _make_agent(prompt=None)
        assert isinstance(agent._prompt, str)

    def test_dict_prompt_raises_if_file_missing(self):
        """Dict prompt path must point to an existing file (legacy .ww behaviour)."""
        with pytest.raises(Exception):
            _make_agent(prompt={"file": "/nonexistent/path.txt"})

    def test_dict_prompt_does_not_append_default(self, tmp_path):
        """Dict path (.ww config) uses the file as-is, not appended onto the default."""
        prompt_file = tmp_path / "full_prompt.txt"
        prompt_file.write_text("Custom full prompt.")

        agent = _make_agent(prompt={"file": str(prompt_file)})
        assert agent._prompt == "Custom full prompt."
