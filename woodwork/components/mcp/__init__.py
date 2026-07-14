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

__all__ = [
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
]
