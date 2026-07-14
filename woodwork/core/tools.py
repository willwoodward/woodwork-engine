"""ToolRegistry and Transport implementations."""

import logging
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


class ToolRegistry:
    """
    Registry of tools available to an agent.

    Tools are registered by name and called via execute().
    """

    def __init__(self) -> None:
        self._tools: Dict[str, Any] = {}

    def register(self, tool: Any) -> None:
        """Register a tool. The tool must have a .name attribute."""
        name = getattr(tool, "name", None)
        if not name:
            raise ValueError(f"Tool {tool!r} has no 'name' attribute")
        self._tools[name] = tool
        log.debug("[ToolRegistry] Registered tool '%s'", name)

    def get(self, name: str) -> Any:
        """Return tool by name, or raise KeyError."""
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not found in registry")
        return self._tools[name]

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def all(self) -> list[Any]:
        return list(self._tools.values())

    async def execute(self, name: str, action: str, inputs: dict[str, Any]) -> Any:
        """Execute a tool by name, forwarding action and inputs."""
        tool = self.get(name)
        # Support both new execute() API and legacy input() API
        if hasattr(tool, "execute"):
            return await tool.execute(action, inputs)
        elif hasattr(tool, "input"):
            import asyncio
            fn = tool.input
            if asyncio.iscoroutinefunction(fn):
                return await fn(action, inputs)
            return fn(action, inputs)
        else:
            raise AttributeError(f"Tool '{name}' has neither execute() nor input()")


class LocalTransport:
    """
    Calls tools directly via a ToolRegistry.

    Used by AgentLoop in the standard single-process deployment.
    """

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    async def call(self, target: str, action: str, inputs: dict[str, Any]) -> Any:
        return await self._registry.execute(target, action, inputs)


class MCPTransport:
    """
    Stub transport for MCP-hosted tools.

    Will be wired up to a live MCPChannel during runtime initialisation.
    At construction time it is inert; the runtime calls set_channel() before
    any agent calls execute().
    """

    def __init__(self) -> None:
        self._channel: Optional[Any] = None

    def set_channel(self, channel: Any) -> None:
        self._channel = channel

    async def call(self, target: str, action: str, inputs: dict[str, Any]) -> Any:
        if self._channel is None:
            raise RuntimeError("MCPTransport has no channel configured")
        return await self._channel.call_tool(target, action, inputs)
