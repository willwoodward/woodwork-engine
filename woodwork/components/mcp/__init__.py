"""
MCP (Model Context Protocol) Components

This package provides comprehensive MCP server integration following the
technical design in docs/design/mcp-server-component.md

Key components:
- MCPServer: Main framework component for MCP server integration
- MCPRegistry: Server discovery and metadata resolution
- MCPChannel: Transport abstraction for STDIO, SSE, WebSocket, HTTP
- MCPServerManager: Lifecycle management and health monitoring
"""

from .mcp_server import MCPServer
from .registry import MCPRegistry, ServerMetadata, TransportType
from .channels import MCPChannel, StdioChannel, SSEChannel
from .manager import MCPServerManager
from .messages import MCPMessage, MCPError

# Legacy compatibility with existing mcp_base and server modules
from .mcp_base import mcp
from .server import mcp_server as LegacyMCPServer

__all__ = [
    # New architecture components
    "MCPServer",
    "MCPRegistry",
    "ServerMetadata",
    "TransportType",
    "MCPChannel",
    "StdioChannel",
    "SSEChannel",
    "MCPServerManager",
    "MCPMessage",
    "MCPError",

    # Legacy components (for backward compatibility)
    "mcp",
    "LegacyMCPServer",
]