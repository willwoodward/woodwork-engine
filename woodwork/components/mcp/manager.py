"""
MCP Server Manager

Handles lifecycle management for MCP servers including registry lookup,
channel creation, and health monitoring.
"""

import asyncio
import logging
from typing import Dict, Optional, Any

from .registry import MCPRegistry, ServerMetadata, TransportType
from .channels import MCPChannel, StdioChannel, SSEChannel, WebSocketChannel, HTTPChannel

log = logging.getLogger(__name__)


class MCPServerManager:
    """Lifecycle management for MCP servers."""

    def __init__(self):
        self.registry = MCPRegistry()
        self._health_check_interval = 30.0  # seconds

    async def create_channel(
        self,
        metadata: ServerMetadata,
        env_vars: Dict[str, str]
    ) -> MCPChannel:
        """
        Create and connect appropriate channel for server.

        Args:
            metadata: Server metadata from registry
            env_vars: Environment variables for server

        Returns:
            Connected MCPChannel instance

        Raises:
            ConnectionError: If channel creation fails
            NotImplementedError: If transport not supported
        """
        transport = metadata.get_preferred_transport()

        log.info(f"[MCPServerManager] Creating {transport.value} channel for {metadata.name}")

        try:
            if transport == TransportType.STDIO:
                return await self._create_stdio_channel(metadata, env_vars)
            elif transport == TransportType.SSE:
                return await self._create_sse_channel(metadata, env_vars)
            elif transport == TransportType.WEBSOCKET:
                return await self._create_websocket_channel(metadata, env_vars)
            elif transport == TransportType.HTTP:
                return await self._create_http_channel(metadata, env_vars)
            else:
                raise NotImplementedError(f"Transport {transport.value} not implemented")

        except Exception as e:
            log.error(f"[MCPServerManager] Failed to create channel for {metadata.name}: {e}")
            raise

    async def _create_stdio_channel(
        self,
        metadata: ServerMetadata,
        env_vars: Dict[str, str]
    ) -> StdioChannel:
        """Create STDIO channel for local Docker container."""
        if not metadata.packages:
            raise ValueError("No packages available for STDIO transport")

        # Use first OCI package
        package = None
        for pkg in metadata.packages:
            if pkg.type == "oci":
                package = pkg
                break

        if not package:
            raise ValueError("No OCI package found for STDIO transport")

        # Validate required environment variables
        self._validate_env_vars(metadata, env_vars)

        # Create and connect channel
        channel = StdioChannel(package, env_vars)
        await channel.connect()

        log.info(f"[MCPServerManager] Created STDIO channel for {metadata.name}")
        return channel

    async def _create_sse_channel(
        self,
        metadata: ServerMetadata,
        env_vars: Dict[str, str]
    ) -> SSEChannel:
        """Create SSE channel for remote server."""
        if not metadata.remotes:
            raise ValueError("No remotes available for SSE transport")

        # Find SSE remote
        sse_remote = None
        for remote in metadata.remotes:
            if remote.type == "sse":
                sse_remote = remote
                break

        if not sse_remote:
            raise ValueError("No SSE remote found")

        # Process header templates with environment variables
        processed_remote = self._process_remote_headers(sse_remote, env_vars)

        # Validate required environment variables
        self._validate_env_vars(metadata, env_vars)

        # Create and connect channel
        channel = SSEChannel(processed_remote)
        await channel.connect()

        log.info(f"[MCPServerManager] Created SSE channel for {metadata.name}")
        return channel

    async def _create_websocket_channel(
        self,
        metadata: ServerMetadata,
        env_vars: Dict[str, str]
    ) -> WebSocketChannel:
        """Create WebSocket channel (future implementation)."""
        raise NotImplementedError("WebSocket transport not yet implemented")

    async def _create_http_channel(
        self,
        metadata: ServerMetadata,
        env_vars: Dict[str, str]
    ) -> HTTPChannel:
        """Create HTTP channel for simple request/response."""
        if not metadata.remotes:
            raise ValueError("No remotes available for HTTP transport")

        # Find HTTP remote
        http_remote = None
        for remote in metadata.remotes:
            if remote.type in ["http", "streamable-http"]:
                http_remote = remote
                break

        if not http_remote:
            raise ValueError("No HTTP remote found")

        # Process header templates with environment variables
        processed_remote = self._process_remote_headers(http_remote, env_vars)

        # Validate required environment variables
        self._validate_env_vars(metadata, env_vars)

        # Create and connect channel
        channel = HTTPChannel(processed_remote)
        await channel.connect()

        log.info(f"[MCPServerManager] Created HTTP channel for {metadata.name}")
        return channel

    def _validate_env_vars(self, metadata: ServerMetadata, env_vars: Dict[str, str]):
        """Validate required environment variables are provided."""
        missing_vars = []

        for env_var in metadata.env_vars:
            if env_var.required and env_var.name not in env_vars:
                missing_vars.append(env_var.name)

        if missing_vars:
            raise ValueError(f"Missing required environment variables: {missing_vars}")

    def _process_remote_headers(self, remote, env_vars: Dict[str, str]):
        """Process header templates with environment variable substitution."""
        from .registry import RemoteInfo

        processed_headers = []
        for header in remote.headers:
            value = header["value"]

            # Simple template substitution for {VAR_NAME}
            for env_name, env_value in env_vars.items():
                if env_value is not None:  # Skip None values
                    placeholder = f"{{{env_name}}}"
                    if placeholder in value:
                        value = value.replace(placeholder, env_value)

            processed_headers.append({
                "name": header["name"],
                "value": value
            })

        return RemoteInfo(
            type=remote.type,
            url=remote.url,
            headers=processed_headers
        )

    async def start_health_monitoring(self, channel: MCPChannel, metadata: ServerMetadata):
        """Start health monitoring for the channel (future implementation)."""
        # TODO: Implement health checks via MCP ping requests
        log.debug(f"[MCPServerManager] Health monitoring not yet implemented for {metadata.name}")

    async def close(self):
        """Close manager and cleanup resources."""
        await self.registry.close()
        log.info("[MCPServerManager] Closed")