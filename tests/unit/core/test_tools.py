"""Tests for woodwork.core.tools."""

import pytest

from woodwork.core.tools import LocalTransport, MCPTransport, ToolRegistry


class _EchoTool:
    name = "echo"
    description = "Returns inputs as-is."

    async def execute(self, action: str, inputs: dict) -> dict:
        return {"action": action, **inputs}


class _LegacyTool:
    name = "legacy"
    description = "Uses old input() API."

    def input(self, action: str, inputs: dict) -> str:
        return f"{action}:{inputs}"


# ──────────────────────────────── ToolRegistry ──────────────────────────


def test_register_and_get():
    reg = ToolRegistry()
    tool = _EchoTool()
    reg.register(tool)
    assert reg.get("echo") is tool


def test_get_missing_raises():
    reg = ToolRegistry()
    with pytest.raises(KeyError):
        reg.get("missing")


def test_register_no_name_raises():
    reg = ToolRegistry()

    class NoName:
        pass

    with pytest.raises(ValueError):
        reg.register(NoName())


def test_names():
    reg = ToolRegistry()
    reg.register(_EchoTool())
    assert "echo" in reg.names()


@pytest.mark.asyncio
async def test_execute_new_api():
    reg = ToolRegistry()
    reg.register(_EchoTool())
    result = await reg.execute("echo", "run", {"key": "val"})
    assert result == {"action": "run", "key": "val"}


@pytest.mark.asyncio
async def test_execute_legacy_api():
    reg = ToolRegistry()
    reg.register(_LegacyTool())
    result = await reg.execute("legacy", "do", {"a": 1})
    assert result == "do:{'a': 1}"


@pytest.mark.asyncio
async def test_execute_missing_raises():
    reg = ToolRegistry()
    with pytest.raises(KeyError):
        await reg.execute("nope", "x", {})


# ──────────────────────────────── LocalTransport ─────────────────────────


@pytest.mark.asyncio
async def test_local_transport():
    reg = ToolRegistry()
    reg.register(_EchoTool())
    transport = LocalTransport(reg)
    result = await transport.call("echo", "ping", {"v": 99})
    assert result["v"] == 99


# ──────────────────────────────── MCPTransport ───────────────────────────


@pytest.mark.asyncio
async def test_mcp_transport_no_channel_raises():
    t = MCPTransport()
    with pytest.raises(RuntimeError):
        await t.call("tool", "act", {})


@pytest.mark.asyncio
async def test_mcp_transport_with_channel():
    class _FakeChannel:
        async def call_tool(self, target, action, inputs):
            return f"{target}/{action}"

    t = MCPTransport()
    t.set_channel(_FakeChannel())
    result = await t.call("my_tool", "run", {})
    assert result == "my_tool/run"
