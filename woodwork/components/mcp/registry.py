"""
MCP Registry Service

Provides access to the Model Context Protocol registry for server discovery and metadata.
Implements caching and version resolution as specified in the technical design.
"""

import time
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import quote
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
    """Information about a local package (OCI container or command)."""

    type: str  # "oci" for Docker, "command" for npx/local commands
    identifier: str
    version: str
    registry_base_url: str = ""
    command: Optional[str] = None  # For command-type: the command to run
    args: Optional[List[str]] = None  # For command-type: command arguments


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
                if package.type in ("oci", "command"):
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
        """Create ServerMetadata from v0.1 registry response.

        Maps the v0.1 API fields to internal format:
        - registryType "npm" → command="npx", args=["-y", identifier]
        - registryType "pypi" → command="uvx", args=[identifier]
        - runtimeHint overrides the default command
        - environmentVariables are aggregated and deduped across packages
        """
        # Default command per registry type
        _REGISTRY_COMMANDS: Dict[str, tuple[str, list[str]]] = {
            "npm": ("npx", ["-y"]),
            "pypi": ("uvx", []),
        }

        packages = []
        seen_env_vars: Dict[str, EnvVar] = {}

        for pkg in server_data.get("packages", []):
            registry_type = pkg.get("registryType", "")
            identifier = pkg.get("name", "")
            version = pkg.get("version", "latest")
            runtime_hint = pkg.get("runtimeHint", "")
            registry_base_url = pkg.get("registryBaseUrl", "")

            # Determine command and args from registry type
            if registry_type in _REGISTRY_COMMANDS:
                default_cmd, prefix_args = _REGISTRY_COMMANDS[registry_type]
                command = runtime_hint or default_cmd
                args = prefix_args + [identifier]
            else:
                command = runtime_hint or registry_type
                args = [identifier]

            packages.append(
                PackageInfo(
                    type="command",
                    identifier=identifier,
                    version=version,
                    registry_base_url=registry_base_url,
                    command=command,
                    args=args,
                )
            )

            # Collect env vars from each package (dedupe by name)
            for env in pkg.get("environmentVariables", []):
                name = env.get("name", "")
                if name and name not in seen_env_vars:
                    seen_env_vars[name] = EnvVar(
                        name=name,
                        required=env.get("isRequired", True),
                        description=env.get("description", ""),
                    )

        remotes = []
        for remote_data in server_data.get("remotes", []):
            headers = []
            for header_data in remote_data.get("headers", []):
                headers.append({"name": header_data["name"], "value": header_data["value"]})

            remotes.append(RemoteInfo(type=remote_data["type"], url=remote_data["url"], headers=headers))

            # Collect env vars from remotes too
            for env in remote_data.get("environmentVariables", []):
                name = env.get("name", "")
                if name and name not in seen_env_vars:
                    seen_env_vars[name] = EnvVar(
                        name=name,
                        required=env.get("isRequired", True),
                        description=env.get("description", ""),
                    )

        return cls(
            name=server_data.get("name", ""),
            version=server_data.get("version_detail", {}).get("version", server_data.get("version", "")),
            description=server_data.get("description", ""),
            packages=packages,
            remotes=remotes,
            env_vars=list(seen_env_vars.values()),
        )


class UnsupportedTransportError(Exception):
    """Raised when no supported transport is available."""

    pass


class MCPRegistry:
    """Client for MCP Registry API with caching."""

    BASE_URL = "https://registry.modelcontextprotocol.io/v0.1"
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

    async def get_server(
        self, name: str, version: str = "latest", toolsets: Optional[str] = None, readonly: Optional[bool] = None
    ) -> ServerMetadata:
        """
        Fetch server metadata from registry with fallback for known servers.

        Uses the v0.1 search endpoint for latest versions, or direct version
        lookup for pinned versions.

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

            if version != "latest":
                # Pinned version: direct lookup
                url = f"{self.BASE_URL}/servers/{quote(name, safe='')}/versions/{quote(version, safe='')}"
                async with http_client.get(url) as response:
                    if response.status == 404:
                        log.debug(f"[MCPRegistry] Server not found in registry: {name}@{version}, using fallback")
                        return self._get_fallback_metadata(name, version, toolsets, readonly)
                    response.raise_for_status()
                    server_data = await response.json()
            else:
                # Latest: use search endpoint
                url = f"{self.BASE_URL}/servers"
                params = {"search": name, "limit": "5", "version": "latest"}
                async with http_client.get(url, params=params) as response:
                    if response.status == 404:
                        log.debug(f"[MCPRegistry] Search returned 404 for {name}, using fallback")
                        return self._get_fallback_metadata(name, version, toolsets, readonly)
                    response.raise_for_status()
                    data = await response.json()

                servers = data.get("servers", [])
                if not servers:
                    log.debug(f"[MCPRegistry] No results for {name}, using fallback")
                    return self._get_fallback_metadata(name, version, toolsets, readonly)

                # Use the first match; the nested "server" object holds metadata
                server_data = servers[0].get("server", servers[0])

            metadata = ServerMetadata.from_registry(server_data)

            # Cache the result
            self._cache[cache_key] = {"metadata": metadata, "timestamp": time.time()}

            log.info(f"[MCPRegistry] Successfully fetched metadata for {name}:{version}")
            return metadata

        except Exception as e:
            log.warning(f"[MCPRegistry] Registry lookup failed for {name}: {e}, trying fallback")
            return self._get_fallback_metadata(name, version, toolsets, readonly)

    def _get_fallback_metadata(
        self, name: str, version: str, toolsets: Optional[str] = None, readonly: Optional[bool] = None
    ) -> ServerMetadata:
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
                {"name": "Accept", "value": "application/json"},
            ]

            # Add toolsets header if specified
            if toolsets is not None:
                log.debug(f"[MCPRegistry] Using configured toolsets: {toolsets}")
                headers.append({"name": "X-MCP-Toolsets", "value": toolsets})
            else:
                log.debug("[MCPRegistry] Using default toolsets: all")
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
                remotes=[RemoteInfo(type="http", url="https://api.githubcopilot.com/mcp/", headers=headers)],
                env_vars=[
                    EnvVar(
                        name="GITHUB_TOKEN",
                        required=True,
                        description="GitHub Personal Access Token with appropriate scopes",
                    )
                ],
            )

        # Google Calendar MCP Server (community, local STDIO via npx)
        if name in ["google/calendar", "nspady/google-calendar-mcp"]:
            return ServerMetadata(
                name=name,
                version=version,
                description="Google Calendar MCP Server (nspady/google-calendar-mcp)",
                packages=[
                    PackageInfo(
                        type="command",
                        identifier="google-calendar-mcp",
                        version=version,
                        command="npx",
                        args=["-y", "@cocal/google-calendar-mcp"],
                    )
                ],
                env_vars=[
                    EnvVar(
                        name="GOOGLE_OAUTH_CREDENTIALS",
                        required=True,
                        description="Path to GCP OAuth client secrets JSON file",
                    )
                ],
            )

        # Google Gmail MCP Server (official, remote HTTP)
        if name in ["google/gmail"]:
            return ServerMetadata(
                name=name,
                version=version,
                description="Google Gmail MCP Server (official)",
                packages=[],
                remotes=[
                    RemoteInfo(
                        type="streamable-http",
                        url="https://gmailmcp.googleapis.com/mcp/v1",
                        headers=[
                            {"name": "Authorization", "value": "Bearer {GOOGLE_ACCESS_TOKEN}"},
                            {"name": "Content-Type", "value": "application/json"},
                        ],
                    )
                ],
                env_vars=[
                    EnvVar(
                        name="GOOGLE_ACCESS_TOKEN",
                        required=True,
                        description="Google OAuth2 access token (use 'woodwork auth google' to obtain)",
                    )
                ],
            )

        # DuckDuckGo MCP Server (free web search, no API key needed)
        if name in ["duckduckgo/mcp-server"]:
            return ServerMetadata(
                name=name,
                version=version,
                description="DuckDuckGo Web Search MCP Server",
                packages=[
                    PackageInfo(
                        type="command",
                        identifier="duckduckgo-mcp-server",
                        version=version,
                        command="uvx",
                        args=["duckduckgo-mcp-server"],
                    )
                ],
                remotes=[],
                env_vars=[],
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
