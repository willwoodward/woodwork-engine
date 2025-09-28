"""
MCP Transport Channels

Unified interface for all MCP transport methods (STDIO, SSE, WebSocket, HTTP).
Implements transport abstraction as specified in the technical design.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, List, Optional, Any
import json

from .messages import MCPMessage, MCPError
from .registry import PackageInfo, RemoteInfo

log = logging.getLogger(__name__)


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
    """Channel for local MCP servers via Docker containers."""

    def __init__(self, package_info: PackageInfo, env_vars: Dict[str, str]):
        self.package_info = package_info
        self.env_vars = env_vars
        self.process: Optional[asyncio.subprocess.Process] = None
        self._connected = False

    async def connect(self) -> None:
        """Start Docker container and establish stdio pipes."""
        if self._connected:
            return

        log.info(f"[StdioChannel] Starting Docker container for {self.package_info.identifier}")

        try:
            # Build Docker command
            docker_cmd = [
                "docker", "run", "-i", "--rm",
                "--name", f"mcp-{self.package_info.identifier.replace('/', '-')}",
            ]

            # Add environment variables
            for key, value in self.env_vars.items():
                docker_cmd.extend(["-e", f"{key}={value}"])

            # Add image
            image_url = f"{self.package_info.registry_base_url}/{self.package_info.identifier}:{self.package_info.version}"
            docker_cmd.append(image_url)

            log.debug(f"[StdioChannel] Docker command: {' '.join(docker_cmd)}")

            # Start process
            self.process = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            self._connected = True
            log.info(f"[StdioChannel] Successfully connected to {self.package_info.identifier}")

        except Exception as e:
            log.error(f"[StdioChannel] Failed to start Docker container: {e}")
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
            return message.id

        except Exception as e:
            log.error(f"[StdioChannel] Failed to send message: {e}")
            raise MCPError({"code": -1, "message": f"Failed to send message: {e}"})

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
    """Channel for MCP servers via HTTP requests (GitHub Copilot style)."""

    def __init__(self, remote_info: RemoteInfo):
        self.remote_info = remote_info
        self.session: Optional[Any] = None  # aiohttp.ClientSession
        self._connected = False
        self._session_id: Optional[str] = None  # MCP session ID for GitHub

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
        """Send message via HTTP POST and return full response."""
        if not self._connected or not self.session:
            raise ConnectionError("Channel not connected")

        try:
            # Prepare request data
            request_data = message.to_dict()
            log.debug(f"[HTTPChannel] Sending request to {self.remote_info.url}")
            log.debug(f"[HTTPChannel] Request data: {request_data}")

            # Prepare headers for this request - start with session headers
            headers = {}

            # Add configured headers from remote info
            for header in self.remote_info.headers:
                headers[header["name"]] = header["value"]

            # Add session ID header for non-initialize requests
            if self._session_id and message.method != "initialize":
                headers["Mcp-Session-Id"] = self._session_id
                log.debug(f"[HTTPChannel] Adding session ID header: {self._session_id}")

            log.debug(f"[HTTPChannel] All request headers: {headers}")

            # Send to the MCP endpoint
            async with self.session.post(self.remote_info.url, json=request_data, headers=headers) as response:
                response_text = await response.text()
                log.debug(f"[HTTPChannel] Response status: {response.status}")
                log.debug(f"[HTTPChannel] Response text: {response_text[:500]}...")

                response.raise_for_status()
                result = await response.json()

                # Extract session ID from initialize response
                if message.method == "initialize" and result.get("result"):
                    # Check for session ID in various possible locations
                    session_id = None

                    # Try common session ID locations
                    if "sessionId" in result.get("result", {}):
                        session_id = result["result"]["sessionId"]
                    elif "session_id" in result.get("result", {}):
                        session_id = result["result"]["session_id"]
                    elif "id" in result.get("result", {}):
                        session_id = result["result"]["id"]

                    # Also check response headers (GitHub uses 'mcp-session-id')
                    session_header = (response.headers.get("mcp-session-id") or
                                    response.headers.get("X-Session-ID") or
                                    response.headers.get("Session-ID"))
                    if session_header:
                        session_id = session_header

                    if session_id:
                        self._session_id = session_id
                        log.info(f"[HTTPChannel] Extracted session ID: {session_id}")
                    else:
                        log.warning(f"[HTTPChannel] No session ID found in initialize response")
                        log.debug(f"[HTTPChannel] Initialize result keys: {list(result.get('result', {}).keys())}")
                        log.debug(f"[HTTPChannel] Response headers: {dict(response.headers)}")

                log.debug(f"[HTTPChannel] Sent message: {message.method}, got response")
                return result

        except Exception as e:
            log.error(f"[HTTPChannel] Failed to send message: {e}")
            raise MCPError({"code": -1, "message": f"Failed to send message: {e}"})

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