"""Tests for woodwork.core.runtime.AsyncRuntime."""

import asyncio
import pytest

from woodwork.core.runtime import AsyncRuntime


class _SimpleComp:
    def __init__(self, name):
        self.name = name
        self.component = "tool"
        self.initialized = False
        self.started = False
        self.stopped = False

    async def initialize(self):
        self.initialized = True

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True


class _InputComp:
    """Minimal input component that yields one query then stops."""

    name = "input"
    component = "input"

    def __init__(self, queries):
        self._queries = iter(queries)
        self.responses = []

    async def stream(self):
        for q in self._queries:
            yield q

    async def respond(self, result):
        self.responses.append(result)


class _AgentComp:
    name = "agent"
    component = "agent"
    started = False

    async def start(self):
        self.started = True

    async def execute(self, action, payload):
        return f"answer:{payload['query']}"


# ──────────────────────────────── lifecycle ──────────────────────────────


@pytest.mark.asyncio
async def test_initialize_and_start_called():
    comp = _SimpleComp("c1")
    runtime = AsyncRuntime()

    # Patch _main_loop so we don't hang
    async def _noop_loop(self=runtime):
        pass

    runtime._main_loop = _noop_loop

    await runtime.start([comp])
    assert comp.initialized
    assert comp.started


@pytest.mark.asyncio
async def test_cleanup_calls_stop():
    comp = _SimpleComp("c2")
    runtime = AsyncRuntime()
    runtime._components = {"c2": comp}
    await runtime._cleanup()
    assert comp.stopped


# ──────────────────────────────── topo sort ──────────────────────────────


def test_topo_sort_no_deps():
    a, b = _SimpleComp("a"), _SimpleComp("b")
    result = AsyncRuntime._topo_sort([a, b], {})
    assert set(c.name for c in result) == {"a", "b"}


def test_topo_sort_with_deps():
    a, b, c = _SimpleComp("a"), _SimpleComp("b"), _SimpleComp("c")
    # c depends on b, b depends on a
    dep_map = {"c": ["b"], "b": ["a"]}
    result = AsyncRuntime._topo_sort([a, b, c], dep_map)
    names = [x.name for x in result]
    assert names.index("a") < names.index("b") < names.index("c")


# ──────────────────────────────── CLI loop ───────────────────────────────


@pytest.mark.asyncio
async def test_cli_loop_routes_to_agent():
    input_comp = _InputComp(["hello"])
    agent_comp = _AgentComp()

    runtime = AsyncRuntime()
    runtime._components = {"input": input_comp, "agent": agent_comp}
    runtime._running = True

    await runtime._run_cli()

    assert input_comp.responses == ["answer:hello"]
