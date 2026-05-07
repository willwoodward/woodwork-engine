"""
MCP Transport Channels

Unified interface for all MCP transport methods (STDIO, SSE, WebSocket, HTTP).
Implements transport abstraction as specified in the technical design.
"""

import asyncio
import asyncio.subprocess
import logging
from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, Optional, Any, cast
import json

from .messages import MCPMessage, MCPError
from .registry import PackageInfo, RemoteInfo

log = logging.getLogger(__name__)


class _MCPAuthRequired(Exception):
    """Internal exception: MCP server returned 401, OAuth flow needed."""

    def __init__(self, www_authenticate: str, resource_url: str):
        self.www_authenticate = www_authenticate
        self.resource_url = resource_url
        super().__init__("MCP server requires authorization")


class MCPChannel(ABC):
    """Abstract base for all MCP transport channels."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to MCP server."""
        pass

    @abstractmethod
    async def send(self, message: MCPMessage) -> str:
        """
        Send message and return request ID.

        Args:
            message: MCP message to send

        Returns:
            Request ID for correlation

        Raises:
            ConnectionError: If channel is not connected
            MCPError: If message sending fails
        """
        pass

    @abstractmethod
    async def listen(self) -> AsyncIterator[MCPMessage]:
        """
        Listen for incoming messages.

        Yields:
            MCPMessage instances as they arrive

        Raises:
            ConnectionError: If channel is not connected
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close connection and cleanup resources."""
        pass


class StdioChannel(MCPChannel):
    """Channel for local MCP servers via STDIO (Docker or command)."""

    def __init__(self, package_info: PackageInfo, env_vars: Dict[str, str]):
        self.package_info = package_info
        self.env_vars = env_vars
        self.process: Optional[asyncio.subprocess.Process] = None
        self._connected = False
        self._stderr_task: Optional[asyncio.Task] = None

    async def connect(self) -> None:
        """Start MCP server process (Docker or command) and establish stdio pipes."""
        if self._connected:
            return

        try:
            if self.package_info.type == "command":
                # Run a local command (e.g., npx)
                cmd = self.package_info.command
                args = self.package_info.args or []
                full_cmd = [cmd] + args

                log.info(f"[StdioChannel] Starting command: {' '.join(full_cmd)}")

                import os

                # Resolve relative file paths in env vars to absolute paths
                resolved_env_vars = {}
                for key, value in self.env_vars.items():
                    if value and ("/" in value or value.endswith(".json")) and not os.path.isabs(value):
                        abs_path = os.path.abspath(value)
                        if os.path.exists(abs_path):
                            resolved_env_vars[key] = abs_path
                            log.debug(f"[StdioChannel] Resolved {key}: {value} -> {abs_path}")
                        else:
                            resolved_env_vars[key] = value
                    else:
                        resolved_env_vars[key] = value

                env = {**os.environ, **resolved_env_vars}

                self.process = await asyncio.create_subprocess_exec(  # type: ignore[misc]
                    *full_cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )
            else:
                # Docker container
                log.info(f"[StdioChannel] Starting Docker container for {self.package_info.identifier}")

                docker_cmd = [
                    "docker",
                    "run",
                    "-i",
                    "--rm",
                    "--name",
                    f"mcp-{self.package_info.identifier.replace('/', '-')}",
                ]

                # Add environment variables
                for key, value in self.env_vars.items():
                    docker_cmd.extend(["-e", f"{key}={value}"])

                # Add image
                image_url = (
                    f"{self.package_info.registry_base_url}/{self.package_info.identifier}:{self.package_info.version}"
                )
                docker_cmd.append(image_url)

                log.debug(f"[StdioChannel] Docker command: {' '.join(docker_cmd)}")

                self.process = await asyncio.create_subprocess_exec(  # type: ignore[misc]
                    *docker_cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

            self._connected = True

            # Start stderr reader to surface auth URLs and errors
            self._stderr_task = asyncio.create_task(self._read_stderr())

            log.info(f"[StdioChannel] Successfully connected to {self.package_info.identifier}")

        except Exception as e:
            log.error(f"[StdioChannel] Failed to start process: {e}")
            raise ConnectionError(f"Failed to connect to MCP server: {e}")

    async def send(self, message: MCPMessage) -> str:
        """Send JSON-RPC message via stdin."""
        if not self._connected or not self.process:
            raise ConnectionError("Channel not connected")

        try:
            json_data = message.to_json() + "\n"
            self.process.stdin.write(json_data.encode())
            await self.process.stdin.drain()

            log.debug(f"[StdioChannel] Sent message: {message.method} (id: {message.id})")
            return cast(str, message.id)

        except Exception as e:
            log.error(f"[StdioChannel] Failed to send message: {e}")
            raise MCPError({"code": -1, "message": f"Failed to send message: {e}"})

    async def _read_stderr(self) -> None:
        """Read stderr from the process, logging output and printing auth URLs."""
        if not self.process or not self.process.stderr:
            return
        try:
            while True:
                line = await self.process.stderr.readline()
                if not line:
                    break
                text = line.decode().strip()
                if text:
                    # Surface auth-related output directly to the user
                    if any(keyword in text.lower() for keyword in ["authorize", "browser", "login", "consent"]):
                        print(f"  [auth] {text}")
                    log.debug(f"[StdioChannel:stderr] {text}")
        except Exception as e:
            log.debug(f"[StdioChannel] Stderr reader stopped: {e}")

    async def listen(self) -> AsyncIterator[MCPMessage]:
        """Read JSON-RPC messages from stdout."""
        if not self._connected or not self.process:
            raise ConnectionError("Channel not connected")

        try:
            while True:
                line = await self.process.stdout.readline()
                if not line:
                    break

                line = line.decode().strip()
                if line:
                    try:
                        message = MCPMessage.from_json(line)
                        log.debug(f"[StdioChannel] Received message: {message.method or 'response'} (id: {message.id})")
                        yield message
                    except json.JSONDecodeError as e:
                        log.warning(f"[StdioChannel] Invalid JSON received: {e}")
                        continue

        except Exception as e:
            log.error(f"[StdioChannel] Error reading messages: {e}")
            raise

    async def close(self) -> None:
        """Close connection and cleanup resources."""
        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                log.warning("[StdioChannel] Process did not terminate gracefully, killing")
                self.process.kill()
                await self.process.wait()
            except Exception as e:
                log.error(f"[StdioChannel] Error closing process: {e}")

        self._connected = False
        self.process = None
        log.info("[StdioChannel] Closed connection")


class SSEChannel(MCPChannel):
    """Channel for remote MCP servers via Server-Sent Events."""

    def __init__(self, remote_info: RemoteInfo):
        self.remote_info = remote_info
        self.session: Optional[Any] = None  # aiohttp.ClientSession
        self.sse_client: Optional[Any] = None  # aiohttp_sse.EventSource
        self._connected = False

    async def connect(self) -> None:
        """Establish SSE connection."""
        if self._connected:
            return

        log.info(f"[SSEChannel] Connecting to {self.remote_info.url}")

        try:
            # Import at runtime to avoid hard dependency
            try:
                import aiohttp
                from aiohttp_sse import sse_client
            except ImportError as import_err:
                log.error("[SSEChannel] Missing required dependencies for SSE transport")
                log.error("[SSEChannel] Please install: pip install aiohttp aiohttp-sse")
                raise ConnectionError("Missing SSE dependencies: aiohttp, aiohttp-sse") from import_err

            # Prepare headers
            headers = {}
            for header in self.remote_info.headers:
                headers[header["name"]] = header["value"]

            # Create session with proper connector
            connector = aiohttp.TCPConnector(limit=10)
            self.session = aiohttp.ClientSession(headers=headers, connector=connector)

            # Create SSE client using correct aiohttp_sse API
            self.sse_client = sse_client(self.session, self.remote_info.url, headers=headers)
            await self.sse_client.__aenter__()
            self._connected = True

            log.info(f"[SSEChannel] Successfully connected to {self.remote_info.url}")

        except ConnectionError:
            # Re-raise our custom connection errors
            raise
        except Exception as e:
            log.error(f"[SSEChannel] Failed to connect: {e}")
            await self._cleanup()
            raise ConnectionError(f"Failed to connect to MCP server: {e}")

    async def send(self, message: MCPMessage) -> str:
        """Send message via HTTP POST."""
        if not self._connected or not self.session:
            raise ConnectionError("Channel not connected")

        try:
            # Send to /send endpoint
            send_url = f"{self.remote_info.url.rstrip('/')}/send"

            async with self.session.post(send_url, json=message.to_dict()) as response:
                response.raise_for_status()
                result = await response.json()

                request_id = result.get("request_id", message.id)
                log.debug(f"[SSEChannel] Sent message: {message.method} (id: {request_id})")
                return request_id

        except Exception as e:
            log.error(f"[SSEChannel] Failed to send message: {e}")
            raise MCPError({"code": -1, "message": f"Failed to send message: {e}"})

    async def listen(self) -> AsyncIterator[MCPMessage]:
        """Listen for SSE events."""
        if not self._connected or not self.sse_client:
            raise ConnectionError("Channel not connected")

        try:
            async for event in self.sse_client:
                if event.type == "message":
                    try:
                        message = MCPMessage.from_json(event.data)
                        log.debug(f"[SSEChannel] Received message: {message.method or 'response'} (id: {message.id})")
                        yield message
                    except json.JSONDecodeError as e:
                        log.warning(f"[SSEChannel] Invalid JSON in SSE event: {e}")
                        continue

        except Exception as e:
            log.error(f"[SSEChannel] Error reading SSE events: {e}")
            raise

    async def close(self) -> None:
        """Close connection and cleanup resources."""
        await self._cleanup()
        log.info("[SSEChannel] Closed connection")

    async def _cleanup(self):
        """Internal cleanup method."""
        if self.sse_client:
            try:
                await self.sse_client.__aexit__(None, None, None)
            except Exception as e:
                log.warning(f"[SSEChannel] Error closing SSE client: {e}")

        if self.session and not self.session.closed:
            try:
                await self.session.close()
            except Exception as e:
                log.warning(f"[SSEChannel] Error closing HTTP session: {e}")

        self._connected = False
        self.sse_client = None
        self.session = None


class WebSocketChannel(MCPChannel):
    """Channel for MCP servers via WebSocket (future implementation)."""

    def __init__(self, remote_info: RemoteInfo):
        self.remote_info = remote_info
        raise NotImplementedError("WebSocket transport not yet implemented")

    async def connect(self) -> None:
        raise NotImplementedError("WebSocket transport not yet implemented")

    async def send(self, message: MCPMessage) -> str:
        raise NotImplementedError("WebSocket transport not yet implemented")

    async def listen(self) -> AsyncIterator[MCPMessage]:
        raise NotImplementedError("WebSocket transport not yet implemented")

    async def close(self) -> None:
        raise NotImplementedError("WebSocket transport not yet implemented")


class HTTPChannel(MCPChannel):
    """Channel for MCP servers via HTTP requests (GitHub Copilot style).

    Supports MCP OAuth 2.1 authorization flow: if the server returns 401,
    discovers the authorization server and obtains a token automatically.
    """

    def __init__(self, remote_info: RemoteInfo):
        self.remote_info = remote_info
        self.session: Optional[Any] = None  # aiohttp.ClientSession
        self._connected = False
        self._session_id: Optional[str] = None  # MCP session ID for GitHub
        self._access_token: Optional[str] = None  # OAuth access token from MCP auth flow
        self._auth_attempted = False  # Prevent infinite auth loops

    async def connect(self) -> None:
        """Establish HTTP connection."""
        if self._connected:
            return

        log.info(f"[HTTPChannel] Connecting to {self.remote_info.url}")

        try:
            # Import at runtime to avoid hard dependency
            try:
                import aiohttp
            except ImportError as import_err:
                log.error("[HTTPChannel] Missing required dependencies for HTTP transport")
                log.error("[HTTPChannel] Please install: pip install aiohttp")
                raise ConnectionError("Missing HTTP dependencies: aiohttp") from import_err

            # Create session with proper connector (headers will be added per-request)
            connector = aiohttp.TCPConnector(limit=10)
            self.session = aiohttp.ClientSession(connector=connector)
            self._connected = True

            log.info(f"[HTTPChannel] Successfully connected to {self.remote_info.url}")

        except ConnectionError:
            # Re-raise our custom connection errors
            raise
        except Exception as e:
            log.error(f"[HTTPChannel] Failed to connect: {e}")
            await self._cleanup()
            raise ConnectionError(f"Failed to connect to MCP server: {e}")

    async def send(self, message: MCPMessage) -> Dict[str, Any]:
        """Send message via HTTP POST and return full response.

        Implements MCP OAuth 2.1 flow: if server returns 401, discovers
        the authorization server and obtains a Bearer token.
        """
        if not self._connected or not self.session:
            raise ConnectionError("Channel not connected")

        try:
            result = await self._send_request(message)
            return result
        except _MCPAuthRequired as auth_err:
            if self._auth_attempted:
                raise MCPError({"code": -1, "message": "MCP OAuth failed after retry"})
            # Attempt MCP OAuth flow
            self._auth_attempted = True
            log.info("[HTTPChannel] Server requires auth, starting MCP OAuth discovery")
            await self._handle_mcp_oauth(auth_err.www_authenticate, auth_err.resource_url)
            # Retry the original request with the new token
            return await self._send_request(message)
        except Exception as e:
            log.debug(f"[HTTPChannel] Failed to send message: {e}")
            raise MCPError({"code": -1, "message": f"Failed to send message: {e}"})

    async def _send_request(self, message: MCPMessage) -> Dict[str, Any]:
        """Send a single HTTP request to the MCP server."""

        request_data = message.to_dict()
        log.debug(f"[HTTPChannel] Sending request to {self.remote_info.url}")
        log.debug(f"[HTTPChannel] Request data: {request_data}")

        # Prepare headers
        headers = {}
        for header in self.remote_info.headers:
            headers[header["name"]] = header["value"]

        # Add OAuth token if we have one from the MCP auth flow
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"

        # Add session ID header for non-initialize requests
        if self._session_id and message.method != "initialize":
            headers["Mcp-Session-Id"] = self._session_id
            log.debug(f"[HTTPChannel] Adding session ID header: {self._session_id}")

        log.debug(f"[HTTPChannel] All request headers: {list(headers.keys())}")

        async with self.session.post(self.remote_info.url, json=request_data, headers=headers) as response:
            response_text = await response.text()
            log.debug(f"[HTTPChannel] Response status: {response.status}")
            log.debug(f"[HTTPChannel] Response text: {response_text[:500]}...")

            # Handle 401 - trigger MCP OAuth flow
            if response.status == 401:
                www_auth = response.headers.get("WWW-Authenticate", "")
                raise _MCPAuthRequired(www_auth, self.remote_info.url)

            response.raise_for_status()
            result = await response.json()

            # Extract session ID from initialize response
            if message.method == "initialize" and result.get("result"):
                session_id = None
                if "sessionId" in result.get("result", {}):
                    session_id = result["result"]["sessionId"]
                elif "session_id" in result.get("result", {}):
                    session_id = result["result"]["session_id"]
                elif "id" in result.get("result", {}):
                    session_id = result["result"]["id"]

                session_header = (
                    response.headers.get("mcp-session-id")
                    or response.headers.get("X-Session-ID")
                    or response.headers.get("Session-ID")
                )
                if session_header:
                    session_id = session_header

                if session_id:
                    self._session_id = session_id
                    log.info(f"[HTTPChannel] Extracted session ID: {session_id}")
                else:
                    log.debug("[HTTPChannel] No session ID found in initialize response")
                    log.debug(f"[HTTPChannel] Initialize result keys: {list(result.get('result', {}).keys())}")
                    log.debug(f"[HTTPChannel] Response headers: {dict(response.headers)}")

            log.debug(f"[HTTPChannel] Sent message: {message.method}, got response")
            return result

    async def _handle_mcp_oauth(self, www_authenticate: str, resource_url: str) -> None:
        """Handle MCP OAuth 2.1 discovery and token acquisition.

        Flow:
        1. Parse WWW-Authenticate for resource_metadata URL
        2. Fetch protected resource metadata
        3. Discover authorization server
        4. Use existing refresh token to get a properly-scoped access token
        """
        import re

        # Step 1: Extract resource_metadata from WWW-Authenticate header
        resource_metadata_url = None
        match = re.search(r'resource_metadata="([^"]+)"', www_authenticate)
        if match:
            resource_metadata_url = match.group(1)
        else:
            # Fallback: try well-known URI
            from urllib.parse import urlparse

            parsed = urlparse(resource_url)
            base = f"{parsed.scheme}://{parsed.netloc}"
            path = parsed.path.rstrip("/")
            resource_metadata_url = f"{base}/.well-known/oauth-protected-resource{path}"

        log.info(f"[HTTPChannel] Fetching resource metadata from: {resource_metadata_url}")

        # Step 2: Fetch protected resource metadata
        async with self.session.get(resource_metadata_url) as resp:
            if resp.status != 200:
                # Try root well-known as fallback
                from urllib.parse import urlparse

                parsed = urlparse(resource_url)
                base = f"{parsed.scheme}://{parsed.netloc}"
                fallback_url = f"{base}/.well-known/oauth-protected-resource"
                log.debug(f"[HTTPChannel] Trying fallback metadata URL: {fallback_url}")
                async with self.session.get(fallback_url) as resp2:
                    resp2.raise_for_status()
                    resource_metadata = await resp2.json()
            else:
                resource_metadata = await resp.json()

        log.debug(f"[HTTPChannel] Resource metadata: {resource_metadata}")

        # Step 3: Get authorization server URL
        auth_servers = resource_metadata.get("authorization_servers", [])
        if not auth_servers:
            raise MCPError({"code": -1, "message": "No authorization servers in resource metadata"})

        auth_server_url = auth_servers[0]
        log.info(f"[HTTPChannel] Authorization server: {auth_server_url}")

        # Discover authorization server metadata
        as_metadata_url = f"{auth_server_url.rstrip('/')}/.well-known/oauth-authorization-server"
        async with self.session.get(as_metadata_url) as resp:
            if resp.status != 200:
                # Try OpenID Connect discovery
                as_metadata_url = f"{auth_server_url.rstrip('/')}/.well-known/openid-configuration"
                async with self.session.get(as_metadata_url) as resp2:
                    resp2.raise_for_status()
                    as_metadata = await resp2.json()
            else:
                as_metadata = await resp.json()

        token_endpoint = as_metadata.get("token_endpoint")
        log.info(f"[HTTPChannel] Token endpoint: {token_endpoint}")

        # Step 4: Get access token using our existing refresh token
        scopes = resource_metadata.get("scopes_supported", [])
        scope_str = " ".join(scopes) if scopes else None

        # Try to use existing credentials from identity store
        try:
            from woodwork.identity.store import load_credentials

            creds = load_credentials("google")
            if creds and creds.get("refresh_token"):
                is_google = "googleapis.com" in token_endpoint
                token_data = {
                    "grant_type": "refresh_token",
                    "refresh_token": creds["refresh_token"],
                    "client_id": creds["client_id"],
                    "client_secret": creds["client_secret"],
                }
                # Google's token endpoint rejects unknown params (scope on refresh, resource)
                if not is_google:
                    if scope_str:
                        token_data["scope"] = scope_str
                    token_data["resource"] = resource_url

                async with self.session.post(token_endpoint, data=token_data) as resp:
                    if resp.status != 200:
                        error_body = await resp.text()
                        log.warning(f"[HTTPChannel] Token refresh failed ({resp.status}): {error_body}")
                        raise MCPError({"code": -1, "message": f"Token refresh failed: {resp.status}"})
                    token_response = await resp.json()

                self._access_token = token_response["access_token"]
                log.info("[HTTPChannel] MCP OAuth: obtained access token via refresh_token")
                return
        except ImportError:
            pass
        except MCPError:
            raise
        except Exception as e:
            log.warning(f"[HTTPChannel] Failed to get token via refresh: {e}")

        # Fallback: check if we have a token in the configured headers
        for header in self.remote_info.headers:
            if header["name"].lower() == "authorization" and header["value"].startswith("Bearer "):
                self._access_token = header["value"].removeprefix("Bearer ")
                log.info("[HTTPChannel] MCP OAuth: using pre-configured Bearer token")
                return

        raise MCPError({"code": -1, "message": "MCP OAuth: unable to obtain access token"})

    async def listen(self) -> AsyncIterator[MCPMessage]:
        """HTTP doesn't support listening - responses come back immediately."""
        # For HTTP-based MCP, we don't have a persistent connection to listen on
        # Responses come back immediately from the send() method
        if False:  # This will never execute
            yield MCPMessage()

    async def close(self) -> None:
        """Close connection and cleanup resources."""
        await self._cleanup()
        log.info("[HTTPChannel] Closed connection")

    async def _cleanup(self):
        """Internal cleanup method."""
        if self.session and not self.session.closed:
            try:
                await self.session.close()
            except Exception as e:
                log.warning(f"[HTTPChannel] Error closing HTTP session: {e}")

        self._connected = False
        self.session = None
        self._session_id = None
