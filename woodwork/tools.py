"""Convenience re-exports for tool components.

Example::

    from woodwork.tools import MCP

    search = MCP(name="search", server="duckduckgo/mcp-server")
"""

from woodwork.components.mcp.mcp_server import MCPServer


class MCP(MCPServer):
    """MCP server component for the woodwork Python API.

    A thin subclass of :class:`~woodwork.components.mcp.mcp_server.MCPServer`
    that provides a shorter, friendlier name.
    """

    def __init__(self, name: str, server: str, **kwargs):
        super().__init__(name=name, server=server, **kwargs)


__all__ = ["MCP"]
