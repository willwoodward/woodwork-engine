"""Tests for woodwork.runtime.Runtime."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from woodwork.runtime import Runtime  # woodwork/runtime/__init__.py


def make_comp(name, model=None, tools=None, input_comp=None):
    """Create a minimal mock component with dependency attributes."""
    comp = MagicMock()
    comp.name = name
    comp._model_component = model
    comp._tools = tools or []
    comp._input_component = input_comp
    comp.component = "agent"
    comp.type = "llm"
    return comp


class TestDiscover:
    def test_single_root_no_deps(self):
        agent = make_comp("agent")
        result = Runtime._discover(agent)
        assert result == [agent]

    def test_discovers_model(self):
        model = make_comp("model")
        agent = make_comp("agent", model=model)
        result = Runtime._discover(agent)
        assert model in result
        assert agent in result
        assert result.index(model) < result.index(agent)

    def test_discovers_tools(self):
        tool = make_comp("tool")
        agent = make_comp("agent", tools=[tool])
        result = Runtime._discover(agent)
        assert tool in result
        assert agent in result
        assert result.index(tool) < result.index(agent)

    def test_discovers_input(self):
        cli = make_comp("cli")
        agent = make_comp("agent", input_comp=cli)
        result = Runtime._discover(agent)
        assert cli in result
        assert agent in result

    def test_deduplicates_shared_dep(self):
        model = make_comp("model")
        agent1 = make_comp("agent1", model=model)
        # Two agents sharing a model — but since we only pass one root, model appears once
        result = Runtime._discover(agent1)
        assert result.count(model) == 1

    def test_list_input_returned_as_is(self):
        a = make_comp("a")
        b = make_comp("b")
        rt = Runtime([a, b])
        assert rt._components == [a, b]


class TestBuildDepMap:
    def test_no_deps(self):
        agent = make_comp("agent")
        rt = Runtime([agent])
        dep_map = rt._build_dep_map()
        assert dep_map == {"agent": []}

    def test_with_model_dep(self):
        model = make_comp("model")
        agent = make_comp("agent", model=model)
        rt = Runtime([model, agent])
        dep_map = rt._build_dep_map()
        assert "model" in dep_map["agent"]
        assert dep_map["model"] == []

    def test_with_tool_dep(self):
        tool = make_comp("search")
        agent = make_comp("agent", tools=[tool])
        rt = Runtime([tool, agent])
        dep_map = rt._build_dep_map()
        assert "search" in dep_map["agent"]


class TestContextManager:
    @pytest.mark.asyncio
    async def test_aenter_calls_setup(self):
        agent = make_comp("agent")
        rt = Runtime([agent])

        mock_ar = MagicMock()
        mock_ar.setup = AsyncMock()
        mock_ar._cleanup = AsyncMock()

        with patch("woodwork.runtime.AsyncRuntime", return_value=mock_ar):
            async with rt as entered:
                assert entered is rt
                mock_ar.setup.assert_called_once()

        mock_ar._cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_aexit_calls_cleanup(self):
        agent = make_comp("agent")
        rt = Runtime([agent])

        mock_ar = MagicMock()
        mock_ar.setup = AsyncMock()
        mock_ar._cleanup = AsyncMock()

        with patch("woodwork.runtime.AsyncRuntime", return_value=mock_ar):
            async with rt:
                pass

        mock_ar._cleanup.assert_called_once()
