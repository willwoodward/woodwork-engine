"""Tests for AgentLoop — pure ReAct execution core."""

import pytest

from woodwork.components.agents.agent_loop import AgentLoop, _extract_json_object, _parse, _resolve_vars
from woodwork.core.events import EventBus
from woodwork.core.tools import ToolRegistry
from woodwork.core.types import AgentContext


# ──────────────────────────────── _parse ─────────────────────────────────


def test_parse_final_answer():
    raw = "Thought: done\nFinal Answer: 42"
    thought, action, is_final = _parse(raw)
    assert is_final
    assert thought == "42"
    assert action is None


def test_parse_action():
    raw = 'Thought: need tool\nAction: {"tool":"echo","action":"run","inputs":{},"output":"x"}'
    thought, action, is_final = _parse(raw)
    assert not is_final
    assert thought == "need tool"
    assert action["tool"] == "echo"


def test_parse_thought_only():
    raw = "Thought: just thinking"
    thought, action, is_final = _parse(raw)
    assert not is_final
    assert action is None
    assert "thinking" in thought


def test_parse_no_thought():
    raw = "Final Answer: done"
    thought, action, is_final = _parse(raw)
    assert is_final
    assert thought == "done"


# ──────────────────────────────── _extract_json_object ───────────────────


def test_extract_json_simple():
    s = '{"a": 1}'
    assert _extract_json_object(s) == '{"a": 1}'


def test_extract_json_nested():
    s = '{"a": {"b": 2}, "c": 3} trailing'
    assert _extract_json_object(s) == '{"a": {"b": 2}, "c": 3}'


# ──────────────────────────────── _resolve_vars ──────────────────────────


def test_resolve_vars_replaces_known():
    resolved = _resolve_vars({"x": "var_name"}, {"var_name": 42})
    assert resolved["x"] == 42


def test_resolve_vars_keeps_literal():
    resolved = _resolve_vars({"x": "hello"}, {})
    assert resolved["x"] == "hello"


# ──────────────────────────────── AgentLoop ──────────────────────────────


class _FakeLLM:
    """LLM that returns scripted responses in order."""

    def __init__(self, responses):
        self._responses = iter(responses)

    async def call(self, system_prompt, history, query):
        return next(self._responses)


class _EchoTool:
    name = "echo"
    description = "echoes"

    async def execute(self, action, inputs):
        return f"ECHO:{action}"


@pytest.mark.asyncio
async def test_single_step_final_answer():
    llm = _FakeLLM(["Thought: got it\nFinal Answer: done"])
    registry = ToolRegistry()
    bus = EventBus()
    loop = AgentLoop(llm, registry, bus)

    ctx = AgentContext(query="hello", session_id="s1")
    result = await loop.run(ctx, "system prompt")
    assert result == "done"


@pytest.mark.asyncio
async def test_tool_call_then_final_answer():
    llm = _FakeLLM([
        'Thought: need echo\nAction: {"tool":"echo","action":"run","inputs":{},"output":"r"}',
        "Thought: got it\nFinal Answer: echoed",
    ])
    registry = ToolRegistry()
    registry.register(_EchoTool())
    bus = EventBus()
    loop = AgentLoop(llm, registry, bus)

    ctx = AgentContext(query="test", session_id="s1")
    result = await loop.run(ctx, "system")
    assert result == "echoed"


@pytest.mark.asyncio
async def test_events_emitted():
    emitted = []

    llm = _FakeLLM([
        'Thought: use tool\nAction: {"tool":"echo","action":"x","inputs":{},"output":"v"}',
        "Final Answer: done",
    ])
    registry = ToolRegistry()
    registry.register(_EchoTool())
    bus = EventBus()
    bus.register_hook("tool.call", lambda p: emitted.append(("tool.call", p)))
    bus.register_hook("agent.thought", lambda p: emitted.append(("thought", p)))

    loop = AgentLoop(llm, registry, bus)
    ctx = AgentContext(query="q", session_id="s1")
    await loop.run(ctx, "sys")

    event_names = [e[0] for e in emitted]
    assert "tool.call" in event_names
    assert "thought" in event_names


@pytest.mark.asyncio
async def test_output_var_stored():
    llm = _FakeLLM([
        'Thought: use tool\nAction: {"tool":"echo","action":"go","inputs":{},"output":"myvar"}',
        "Final Answer: done",
    ])
    registry = ToolRegistry()
    registry.register(_EchoTool())
    bus = EventBus()
    loop = AgentLoop(llm, registry, bus)
    ctx = AgentContext(query="q", session_id="s1")
    await loop.run(ctx, "sys")
    assert "myvar" in ctx.variables


@pytest.mark.asyncio
async def test_forces_final_after_no_action():
    # LLM keeps returning thought-only; should force final after MAX_NO_ACTION
    llm = _FakeLLM(["Thought: still thinking"] * 10)
    registry = ToolRegistry()
    bus = EventBus()
    loop = AgentLoop(llm, registry, bus)
    ctx = AgentContext(query="q", session_id="s1")
    result = await loop.run(ctx, "sys")
    assert "thinking" in result
