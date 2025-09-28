"""
MCP Registry Service

Provides access to the Model Context Protocol registry for server discovery and metadata.
Implements caching and version resolution as specified in the technical design.
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import aiohttp

log = logging.getLogger(__name__)


class TransportType(Enum):
    """Supported transport types for MCP servers."""
    STDIO = "stdio"
    SSE = "sse"
    WEBSOCKET = "websocket"
    HTTP = "http"


@dataclass
class PackageInfo:
    """Information about a local package (OCI container)."""
    type: str
    identifier: str
    version: str
    registry_base_url: str


@dataclass
class RemoteInfo:
    """Information about a remote server endpoint."""
    type: str
    url: str
    headers: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class EnvVar:
    """Environment variable requirement."""
    name: str
    required: bool = True
    description: str = ""


@dataclass
class ServerMetadata:
    """Complete metadata for an MCP server."""
    name: str
    version: str
    description: str
    packages: List[PackageInfo] = field(default_factory=list)
    remotes: List[RemoteInfo] = field(default_factory=list)
    env_vars: List[EnvVar] = field(default_factory=list)

    def get_preferred_transport(self) -> TransportType:
        """Select optimal transport method based on availability and performance."""
        # Prefer local packages for better performance/security
        if self.packages:
            for package in self.packages:
                if package.type == "oci":
                    return TransportType.STDIO

        # Fallback to remote endpoints
        if self.remotes:
            for remote in self.remotes:
                if remote.type == "sse":
                    return TransportType.SSE
                elif remote.type in ["http", "streamable-http"]:
                    return TransportType.HTTP
                elif remote.type == "websocket":
                    return TransportType.WEBSOCKET

        # Provide helpful error message
        available_transports = []
        if self.packages:
            available_transports.extend([f"package:{pkg.type}" for pkg in self.packages])
        if self.remotes:
            available_transports.extend([f"remote:{remote.type}" for remote in self.remotes])

        if available_transports:
            error_msg = f"No supported transport for {self.name}. Available: {available_transports}. Supported: oci packages, sse/websocket/streamable-http remotes"
        else:
            error_msg = f"No transports available for {self.name}. Server metadata may be incomplete"

        raise UnsupportedTransportError(error_msg)

    @classmethod
    def from_registry(cls, server_data: Dict[str, Any]) -> "ServerMetadata":
        """Create ServerMetadata from registry response."""
        packages = []
        for package_data in server_data.get("packages", []):
            packages.append(PackageInfo(
                type=package_data["type"],
                identifier=package_data["identifier"],
                version=package_data["version"],
                registry_base_url=package_data.get("registry_base_url", "")
            ))

        remotes = []
        for remote_data in server_data.get("remotes", []):
            headers = []
            for header_data in remote_data.get("headers", []):
                headers.append({
                    "name": header_data["name"],
                    "value": header_data["value"]
                })

            remotes.append(RemoteInfo(
                type=remote_data["type"],
                url=remote_data["url"],
                headers=headers
            ))

        env_vars = []
        for env_data in server_data.get("env_vars", []):
            env_vars.append(EnvVar(
                name=env_data["name"],
                required=env_data.get("required", True),
                description=env_data.get("description", "")
            ))

        return cls(
            name=server_data["name"],
            version=server_data["version"],
            description=server_data.get("description", ""),
            packages=packages,
            remotes=remotes,
            env_vars=env_vars
        )


class UnsupportedTransportError(Exception):
    """Raised when no supported transport is available."""
    pass


class MCPRegistry:
    """Client for MCP Registry API with caching."""

    BASE_URL = "https://registry.modelcontextprotocol.io/v0"
    CACHE_TTL = 3600  # 1 hour

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._http_client: Optional[aiohttp.ClientSession] = None

    async def _get_http_client(self) -> aiohttp.ClientSession:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.closed:
            # Configure connector with proper cleanup
            connector = aiohttp.TCPConnector(limit=10)
            self._http_client = aiohttp.ClientSession(connector=connector)
        return self._http_client

    async def get_server(self, name: str, version: str = "latest", toolsets: Optional[str] = None, readonly: Optional[bool] = None) -> ServerMetadata:
        """
        Fetch server metadata from registry with fallback for known servers.

        Args:
            name: Server name (e.g., "io.github.github/mcp-server")
            version: Version string or "latest"
            toolsets: Comma-separated list of toolsets to enable (GitHub MCP specific)
            readonly: Enable only read tools (GitHub MCP specific)

        Returns:
            ServerMetadata for the server

        Raises:
            ValueError: If server not found
            aiohttp.ClientError: If registry request fails
        """
        cache_key = f"{name}:{version}:{toolsets}:{readonly}"

        # Check cache first
        if cache_key in self._cache:
            cached_data = self._cache[cache_key]
            if time.time() - cached_data["timestamp"] < self.CACHE_TTL:
                log.debug(f"[MCPRegistry] Using cached metadata for {name}:{version}")
                return cached_data["metadata"]

        # Try registry first, with fallback to known servers
        try:
            log.info(f"[MCPRegistry] Fetching metadata for {name}:{version}")

            http_client = await self._get_http_client()
            # Use correct server endpoint format
            server_id = name.replace('/', '-')  # Convert name to valid server ID
            url = f"{self.BASE_URL}/server/{server_id}"

            async with http_client.get(url) as response:
                if response.status == 404:
                    log.warning(f"[MCPRegistry] Server not found in registry: {name}, trying fallback")
                    return self._get_fallback_metadata(name, version, toolsets, readonly)

                response.raise_for_status()
                data = await response.json()

            # Registry returns single server object, not array
            metadata = ServerMetadata.from_registry(data)

            # Cache the result
            self._cache[cache_key] = {
                "metadata": metadata,
                "timestamp": time.time()
            }

            log.info(f"[MCPRegistry] Successfully fetched metadata for {name}:{version}")
            return metadata

        except Exception as e:
            log.warning(f"[MCPRegistry] Registry lookup failed for {name}: {e}, trying fallback")
            return self._get_fallback_metadata(name, version, toolsets, readonly)


    def _get_fallback_metadata(self, name: str, version: str, toolsets: Optional[str] = None, readonly: Optional[bool] = None) -> ServerMetadata:
        """
        Get fallback metadata for known MCP servers when registry is unavailable.

        Args:
            name: Server name
            version: Version string
            toolsets: Comma-separated list of toolsets to enable (GitHub MCP specific)
            readonly: Enable only read tools (GitHub MCP specific)

        Returns:
            ServerMetadata with basic configuration

        Raises:
            ValueError: If server not recognized
        """
        log.info(f"[MCPRegistry] Using fallback metadata for {name}:{version}")
        log.debug(f"[MCPRegistry] Fallback parameters - toolsets: {toolsets}, readonly: {readonly}")

        # GitHub MCP Server (GitHub Copilot MCP Server) - temporary until in registry
        if name in ["github/mcp-server"]:
            # Build headers dynamically based on configuration
            headers = [
                {"name": "Authorization", "value": "Bearer {GITHUB_TOKEN}"},
                {"name": "Content-Type", "value": "application/json"},
                {"name": "Accept", "value": "application/json"}
            ]

            # Add toolsets header if specified
            if toolsets is not None:
                log.debug(f"[MCPRegistry] Using configured toolsets: {toolsets}")
                headers.append({"name": "X-MCP-Toolsets", "value": toolsets})
            else:
                log.debug(f"[MCPRegistry] Using default toolsets: all")
                headers.append({"name": "X-MCP-Toolsets", "value": "all"})

            # Add readonly header if specified
            if readonly is not None:
                readonly_value = "true" if readonly else "false"
                headers.append({"name": "X-MCP-Readonly", "value": readonly_value})
            else:
                headers.append({"name": "X-MCP-Readonly", "value": "false"})

            # Build description based on configuration
            description_parts = ["GitHub Copilot MCP Server"]
            if toolsets:
                description_parts.append(f"Toolsets: {toolsets}")
            else:
                description_parts.append("All GitHub tools")
            if readonly:
                description_parts.append("(readonly)")

            return ServerMetadata(
                name=name,
                version=version,
                description=" - ".join(description_parts),
                packages=[],
                remotes=[
                    RemoteInfo(
                        type="http",
                        url="https://api.githubcopilot.com/mcp/",
                        headers=headers
                    )
                ],
                env_vars=[
                    EnvVar(
                        name="GITHUB_TOKEN",
                        required=True,
                        description="GitHub Personal Access Token with appropriate scopes"
                    )
                ]
            )

        raise ValueError(f"Server '{name}' not found in registry and no fallback available")

    async def close(self):
        """Close HTTP client and cleanup resources."""
        if self._http_client and not self._http_client.closed:
            await self._http_client.close()
            log.debug("[MCPRegistry] Closed HTTP client")

    def clear_cache(self):
        """Clear the metadata cache."""
        self._cache.clear()
        log.debug("[MCPRegistry] Cleared metadata cache")