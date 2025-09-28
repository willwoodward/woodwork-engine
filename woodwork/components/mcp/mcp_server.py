"""
MCP Server Component

Main framework component for integrating MCP servers into the woodwork engine.
Implements the architecture described in docs/design/mcp-server-component.md
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, Any, Optional, List

from woodwork.components.component import component
from woodwork.interfaces.tool_interface import tool_interface
from woodwork.utils import format_kwargs

from .registry import MCPRegistry, ServerMetadata
from .manager import MCPServerManager
from .channels import MCPChannel
from .messages import MCPMessage, MCPError

log = logging.getLogger(__name__)


class MCPServer(component, tool_interface):
    """Framework component for MCP servers with registry integration."""

    def __init__(
        self,
        name: str,
        server: str,
        version: str = "latest",
        env: Optional[Dict[str, str]] = None,
        auth: Optional[Dict[str, str]] = None,
        toolsets: Optional[str] = None,
        readonly: Optional[bool] = None,
        **config
    ):
        """
        Initialize MCP server component.

        Args:
            name: Component name
            server: Server identifier (e.g., "io.github.github/mcp-server")
            version: Server version or "latest"
            env: Environment variables
            auth: Authentication variables
            toolsets: Comma-separated list of toolsets to enable (e.g., "repos,issues")
            readonly: Enable only read tools (GitHub MCP specific)
            **config: Additional component configuration
        """
        # Validate required parameters
        if not server:
            raise ValueError("server name is required")
        if not version:
            raise ValueError("version is required")

        # Setup component configuration
        format_kwargs(config, component="mcp_server", type="mcp_server")
        super().__init__(name=name, **config)

        # MCP-specific configuration
        self.server_name = server
        self.server_version = version
        self.env_vars = env or {}
        self.auth_vars = auth or {}
        self.toolsets = toolsets
        self.readonly = readonly

        log.debug(f"[MCPServer] Initialized with toolsets: {toolsets}, readonly: {readonly}")

        # Combined environment variables
        self.all_env_vars = {**self.env_vars, **self.auth_vars}

        # MCP infrastructure
        self.registry = MCPRegistry()
        self.manager = MCPServerManager()
        self.channel: Optional[MCPChannel] = None
        self.metadata: Optional[ServerMetadata] = None

        # Message correlation for request/response
        self.pending_requests: Dict[str, asyncio.Future] = {}

        # Component state
        self._started = False
        self._message_listener_task: Optional[asyncio.Task] = None
        self._initialized = False
        self._blocking_startup_task: Optional[asyncio.Task] = None

        # Capability caching
        self._capabilities: Optional[Dict[str, Any]] = None
        self._capabilities_fetched = False

        log.info(f"[MCPServer] Initialized {name} for server {server}:{version}")

        # Trigger BLOCKING eager initialization for immediate tool discovery
        self._trigger_blocking_initialization()

    def _trigger_blocking_initialization(self) -> None:
        """Trigger blocking initialization to ensure capabilities are available immediately."""
        try:
            # Check if we're in an asyncio event loop
            loop = asyncio.get_running_loop()
            if loop.is_running():
                # Run initialization synchronously to block until complete
                log.info(f"[MCPServer] Running blocking initialization for {self.name} to ensure tool discovery")
                task = asyncio.create_task(self._blocking_startup_sequence())
                # Don't await here - let it run but ensure it completes before description is called
                self._blocking_startup_task = task
            else:
                log.debug(f"[MCPServer] No event loop running, skipping blocking initialization for {self.name}")
        except RuntimeError:
            # No event loop running, that's ok
            log.debug(f"[MCPServer] No event loop available for blocking initialization of {self.name}")
        except Exception as e:
            log.warning(f"[MCPServer] Failed to trigger blocking initialization for {self.name}: {e}")

    async def _blocking_startup_sequence(self) -> None:
        """Complete startup sequence that blocks until capabilities are available."""
        try:
            # Small delay to let component initialization complete
            await asyncio.sleep(0.05)

            if not self._started:
                log.info(f"[MCPServer] Blocking startup for {self.name} to ensure immediate tool discovery")
                await self.start()

                # Explicitly fetch capabilities after starting
                if self._started and not self._capabilities_fetched:
                    await self._fetch_capabilities()

                # Wait for capabilities with timeout
                max_wait = 5.0  # Wait up to 5 seconds for capabilities
                wait_increment = 0.05
                waited = 0.0

                while not self._capabilities_fetched and waited < max_wait:
                    await asyncio.sleep(wait_increment)
                    waited += wait_increment

                if self._capabilities_fetched:
                    tool_count = len(self._capabilities.get("tools", []))
                    log.info(f"[MCPServer] Blocking startup complete for {self.name}: {tool_count} tools discovered")
                else:
                    log.warning(f"[MCPServer] Blocking startup timeout for {self.name}: capabilities not ready within {max_wait}s")

        except Exception as e:
            log.warning(f"[MCPServer] Blocking startup failed for {self.name}: {e}")

    async def _wait_for_capabilities(self, timeout: float = 5.0) -> bool:
        """Wait for capabilities to be loaded, used by description property."""
        if self._capabilities_fetched:
            return True

        # If we have a blocking startup task, wait for it
        if hasattr(self, '_blocking_startup_task') and self._blocking_startup_task:
            try:
                await asyncio.wait_for(self._blocking_startup_task, timeout=timeout)
                return self._capabilities_fetched
            except asyncio.TimeoutError:
                log.warning(f"[MCPServer] Timed out waiting for blocking startup of {self.name}")
                return False
            except Exception as e:
                log.warning(f"[MCPServer] Error waiting for blocking startup of {self.name}: {e}")
                return False

        return False


    async def start(self) -> None:
        """Initialize and start MCP server connection."""
        if self._started:
            log.debug(f"[MCPServer] {self.name} already started")
            return

        log.info(f"[MCPServer] Starting {self.name} ({self.server_name}:{self.server_version})")

        try:
            # Registry resolution
            log.debug(f"[MCPServer] Resolving {self.server_name}:{self.server_version} from registry")
            log.debug(f"[MCPServer] Passing to registry - toolsets: {self.toolsets}, readonly: {self.readonly}")
            self.metadata = await self.registry.get_server(self.server_name, self.server_version, self.toolsets, self.readonly)

            # Channel creation
            log.debug(f"[MCPServer] Creating channel for {self.server_name}")
            self.channel = await self.manager.create_channel(self.metadata, self.all_env_vars)

            # Start message listener
            self._message_listener_task = asyncio.create_task(self._message_listener())

            # Initialize MCP session
            await self._initialize_mcp_session()

            # Fetch capabilities in background
            asyncio.create_task(self._fetch_capabilities())

            self._started = True
            log.info(f"[MCPServer] Started {self.name} successfully")

        except Exception as e:
            log.error(f"[MCPServer] Failed to start {self.name}: {e}")
            await self._cleanup()
            raise

    async def close(self) -> None:
        """Close MCP server and cleanup resources."""
        if not self._started:
            return

        log.info(f"[MCPServer] Closing {self.name}")
        await self._cleanup()

    async def _cleanup(self):
        """Internal cleanup method."""
        # Cancel message listener
        if self._message_listener_task and not self._message_listener_task.done():
            self._message_listener_task.cancel()
            try:
                await self._message_listener_task
            except asyncio.CancelledError:
                pass

        # Close channel
        if self.channel:
            await self.channel.close()
            self.channel = None

        # Cancel pending requests
        for future in self.pending_requests.values():
            if not future.done():
                future.cancel()
        self.pending_requests.clear()

        # Close manager and registry
        await self.manager.close()

        self._started = False
        self._initialized = False
        log.info(f"[MCPServer] Closed {self.name}")

    async def _initialize_mcp_session(self) -> None:
        """Initialize MCP session with the server."""
        if self._initialized or not self.channel:
            return

        log.info(f"[MCPServer] Initializing MCP session for {self.name}")

        try:
            request_id = str(uuid.uuid4())
            message = MCPMessage(
                id=request_id,
                method="initialize",
                params={
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "roots": {
                            "listChanged": True
                        },
                        "sampling": {}
                    },
                    "clientInfo": {
                        "name": "woodwork-engine",
                        "version": "1.0.0"
                    }
                }
            )

            # For HTTP channels, send and get immediate response
            if hasattr(self.channel, 'send') and 'HTTP' in str(type(self.channel)):
                log.debug(f"[MCPServer] Sending MCP initialize request for {self.name}")
                result = await self.channel.send(message)

                # Check if initialization was successful
                if isinstance(result, dict) and result.get("result"):
                    log.info(f"[MCPServer] MCP session initialized successfully for {self.name}")
                    log.debug(f"[MCPServer] Server capabilities: {result.get('result', {}).get('capabilities', {})}")
                    self._initialized = True
                else:
                    log.warning(f"[MCPServer] MCP initialization response: {result}")
                    self._initialized = True  # Continue anyway
            else:
                # For other transports, use request/response correlation
                future = asyncio.Future()
                self.pending_requests[request_id] = future

                await self.channel.send(message)

                # Wait for response with timeout
                try:
                    result = await asyncio.wait_for(future, timeout=10.0)
                    log.info(f"[MCPServer] MCP session initialized successfully for {self.name}")
                    self._initialized = True
                except asyncio.TimeoutError:
                    log.warning(f"[MCPServer] MCP initialization timeout for {self.name}")
                    self._initialized = True  # Continue anyway
                finally:
                    self.pending_requests.pop(request_id, None)

        except Exception as e:
            log.error(f"[MCPServer] Failed to initialize MCP session for {self.name}: {e}")
            # Don't fail startup completely, some servers might work without explicit init
            self._initialized = True

    async def _framework_auto_start(self) -> None:
        """Auto-start server in framework context for tool discovery."""
        try:
            # Minimal delay to let framework initialization complete
            await asyncio.sleep(0.1)
            if not self._started:
                log.info(f"[MCPServer] Framework auto-starting {self.name} for tool discovery")
                try:
                    await self.start()

                    # Wait a bit more for capabilities to be fetched
                    max_wait = 3.0  # Maximum wait time in seconds
                    wait_increment = 0.1
                    waited = 0.0

                    while not self._capabilities_fetched and waited < max_wait:
                        await asyncio.sleep(wait_increment)
                        waited += wait_increment

                    if self._capabilities_fetched:
                        tool_count = len(self._capabilities.get("tools", []))
                        log.info(f"[MCPServer] Framework auto-start complete for {self.name}: {tool_count} tools discovered")
                    else:
                        log.warning(f"[MCPServer] Framework auto-start timeout for {self.name}: capabilities not fetched within {max_wait}s")

                except Exception as start_error:
                    log.warning(f"[MCPServer] Framework auto-start failed during server start for {self.name}: {start_error}")
                    # Don't re-raise, allow component to work in lazy mode

        except Exception as e:
            log.warning(f"[MCPServer] Framework auto-start failed for {self.name}: {e}")

    async def _auto_start_for_description(self) -> None:
        """Auto-start server in background for description generation."""
        try:
            if not self._started:
                await self.start()
        except Exception as e:
            log.warning(f"[MCPServer] Background startup for description failed: {e}")

    # Tool interface implementation
    async def input(self, action: str, inputs: Dict[str, Any]) -> Any:
        """
        Handle framework input calls as MCP tool calls.

        Args:
            action: Tool name to call
            inputs: Tool arguments

        Returns:
            Tool result from MCP server

        Raises:
            ConnectionError: If not connected to MCP server
            MCPError: If tool call fails
            TimeoutError: If tool call times out
        """
        # Auto-start if not already started (lazy initialization)
        if not self._started:
            log.info(f"[MCPServer] Auto-starting {self.name} on first use")
            await self.start()

        if not self.channel:
            raise ConnectionError(f"MCP server {self.name} failed to start")

        request_id = str(uuid.uuid4())

        log.debug(f"[MCPServer] Calling tool {action} on {self.name} (request: {request_id})")

        # Create MCP tool call message
        message = MCPMessage(
            id=request_id,
            method="tools/call",
            params={
                "name": action,
                "arguments": inputs
            }
        )

        # Create future for response correlation
        future = asyncio.Future()
        self.pending_requests[request_id] = future

        try:
            # For HTTP channels, response comes back immediately
            from .channels import HTTPChannel
            if isinstance(self.channel, HTTPChannel):
                # Send and get immediate response
                response = await self.channel.send(message)
                log.debug(f"[MCPServer] Tool call {action} completed on {self.name} (HTTP)")

                # Extract result from MCP response
                if "error" in response:
                    error = MCPError(response["error"])
                    raise error
                else:
                    result = response.get("result", response)
                    # Convert complex results to strings for agent consumption
                    if isinstance(result, (dict, list)):
                        import json
                        return json.dumps(result, indent=2, ensure_ascii=False)
                    return str(result) if result is not None else ""
            else:
                # Send request for persistent connections (SSE, WebSocket, STDIO)
                await self.channel.send(message)

                # Wait for response with timeout
                result = await asyncio.wait_for(future, timeout=30.0)

                log.debug(f"[MCPServer] Tool call {action} completed on {self.name}")

                # Convert complex results to strings for agent consumption
                if isinstance(result, (dict, list)):
                    import json
                    return json.dumps(result, indent=2, ensure_ascii=False)
                return str(result) if result is not None else ""

        except asyncio.TimeoutError:
            log.error(f"[MCPServer] Tool call {action} timed out on {self.name}")
            raise TimeoutError(f"Tool call {action} timed out after 30 seconds")

        except Exception as e:
            log.error(f"[MCPServer] Tool call {action} failed on {self.name}: {e}")
            raise

        finally:
            # Cleanup pending request
            self.pending_requests.pop(request_id, None)

    @property
    def description(self) -> str:
        """Get component description with available capabilities."""
        # Try to wait for capabilities if we have a blocking startup task
        if not self._capabilities_fetched and hasattr(self, '_blocking_startup_task') and self._blocking_startup_task:
            try:
                # Check if we're in an event loop and can wait
                loop = asyncio.get_running_loop()
                if loop.is_running() and not self._blocking_startup_task.done():
                    # Create a quick check to see if capabilities are ready
                    # without blocking too long
                    for i in range(100):  # Check for up to 5 seconds (100 * 0.05s)
                        if self._capabilities_fetched or self._blocking_startup_task.done():
                            break
                        # Very brief sleep to let other tasks run
                        import time
                        time.sleep(0.05)
            except RuntimeError:
                # No event loop, can't wait
                pass
            except Exception as e:
                log.debug(f"[MCPServer] Error checking startup task in description for {self.name}: {e}")

        if self._capabilities and self._capabilities_fetched:
            # Build detailed description from capabilities in debug script format
            description_parts = []

            # Base description
            if self.metadata:
                description_parts.append(f"MCP Server: {self.metadata.description}")
            else:
                description_parts.append(f"MCP Server: {self.server_name}:{self.server_version}")

            # Add tools with detailed format like debug script
            tools = self._capabilities.get("tools", [])

            if tools:
                description_parts.append(f"\n\nAvailable tools ({len(tools)}):")
                for i, tool in enumerate(tools, 1):
                    name = tool.get("name", "unnamed")
                    desc = tool.get("description", "No description")

                    # Escape curly braces in descriptions to prevent LangChain template errors
                    escaped_desc = desc.replace("{", "{{").replace("}", "}}")

                    tool_detail = f"\n{i:2d}. {name}"
                    tool_detail += f"\n    Description: {escaped_desc}"

                    # Show parameters with types if available
                    if "inputSchema" in tool:
                        schema = tool["inputSchema"]
                        if "properties" in schema:
                            properties = schema["properties"]
                            required = schema.get("required", [])

                            # Format parameters with types
                            param_parts = []
                            required_parts = []

                            for param_name, param_def in properties.items():
                                param_type = param_def.get("type", "unknown")
                                param_desc = param_def.get("description", "")

                                # Escape curly braces in parameter descriptions to prevent LangChain template errors
                                escaped_param_desc = param_desc.replace("{", "{{").replace("}", "}}")

                                # Format as: param_name (type, required/optional) - description
                                param_status = "required" if param_name in required else "optional"
                                if escaped_param_desc:
                                    param_parts.append(f"{param_name} ({param_type}, {param_status}) - {escaped_param_desc}")
                                else:
                                    param_parts.append(f"{param_name} ({param_type}, {param_status})")

                                if param_name in required:
                                    required_parts.append(param_name)

                            if param_parts:
                                tool_detail += f"\n    Parameters: {'; '.join(param_parts)}"
                            if required_parts:
                                tool_detail += f"\n    Required: {', '.join(required_parts)}"

                    description_parts.append(tool_detail)

            # Add resources if available
            resources = self._capabilities.get("resources", [])
            if resources:
                description_parts.append(f"\n\nAvailable resources ({len(resources)}):")
                for i, resource in enumerate(resources, 1):
                    name = resource.get("name", "unnamed")
                    uri = resource.get("uri", "no-uri")
                    desc = resource.get("description", "No description")
                    mime_type = resource.get("mimeType", "unknown")

                    # Escape curly braces in URI and description to prevent LangChain template errors
                    escaped_uri = uri.replace("{", "{{").replace("}", "}}")
                    escaped_desc = desc.replace("{", "{{").replace("}", "}}")

                    resource_detail = f"\n{i:2d}. {name} ({escaped_uri})"
                    resource_detail += f"\n    Type: {mime_type}"
                    resource_detail += f"\n    Description: {escaped_desc}"
                    description_parts.append(resource_detail)

            # Add prompts if available
            prompts = self._capabilities.get("prompts", [])
            if prompts:
                description_parts.append(f"\n\nAvailable prompts ({len(prompts)}):")
                for i, prompt in enumerate(prompts, 1):
                    name = prompt.get("name", "unnamed")
                    desc = prompt.get("description", "No description")

                    # Escape curly braces in descriptions to prevent LangChain template errors
                    escaped_desc = desc.replace("{", "{{").replace("}", "}}")

                    prompt_detail = f"\n{i:2d}. {name}"
                    prompt_detail += f"\n    Description: {escaped_desc}"

                    # Show arguments if available
                    if "arguments" in prompt:
                        args = [arg.get("name", "unnamed") for arg in prompt["arguments"]]
                        if args:
                            prompt_detail += f"\n    Arguments: {', '.join(args)}"
                    description_parts.append(prompt_detail)

            return "".join(description_parts)

        # Fallback description while capabilities are loading or failed
        if self._capabilities_fetched and self._capabilities:
            # Capabilities were fetched but are empty
            base = f"MCP Server: {self.metadata.description}" if self.metadata else f"MCP Server: {self.server_name}:{self.server_version}"
            return f"{base} (no capabilities available)"
        elif self._started:
            # Server is started but capabilities still loading
            base = f"MCP Server: {self.metadata.description}" if self.metadata else f"MCP Server: {self.server_name}:{self.server_version}"
            return f"{base} (loading capabilities...)"
        else:
            # Server not started yet (this should be rare with blocking initialization)
            base = f"MCP Server: {self.metadata.description}" if self.metadata else f"MCP Server: {self.server_name}:{self.server_version}"
            # Check if we're in blocking startup process
            return f"{base} (initializing for tool discovery...)"

    # MCP-specific methods
    async def list_tools(self) -> Dict[str, Any]:
        """List available tools from MCP server."""
        # Auto-start if not already started
        if not self._started:
            await self.start()

        if not self.channel:
            raise ConnectionError(f"MCP server {self.name} failed to start")

        request_id = str(uuid.uuid4())
        message = MCPMessage(
            id=request_id,
            method="tools/list",
            params={}
        )

        # Handle HTTP channels differently (immediate response)
        if hasattr(self.channel, 'send') and 'HTTP' in str(type(self.channel)):
            try:
                result = await self.channel.send(message)
                # Extract the result part for JSON-RPC response
                if isinstance(result, dict) and "result" in result:
                    return result["result"]
                elif isinstance(result, dict) and "error" in result:
                    error = result["error"]
                    raise MCPError(error)
                else:
                    return result
            except Exception as e:
                if isinstance(e, MCPError):
                    raise
                raise MCPError({"code": -1, "message": f"Failed to list tools: {e}"})
        else:
            # Handle other transports with request/response correlation
            future = asyncio.Future()
            self.pending_requests[request_id] = future

            try:
                await self.channel.send(message)
                result = await asyncio.wait_for(future, timeout=10.0)
                return result
            finally:
                self.pending_requests.pop(request_id, None)

    async def list_resources(self) -> Dict[str, Any]:
        """List available resources from MCP server."""
        # Auto-start if not already started
        if not self._started:
            await self.start()

        if not self.channel:
            raise ConnectionError(f"MCP server {self.name} failed to start")

        request_id = str(uuid.uuid4())
        message = MCPMessage(
            id=request_id,
            method="resources/list",
            params={}
        )

        # Handle HTTP channels differently (immediate response)
        if hasattr(self.channel, 'send') and 'HTTP' in str(type(self.channel)):
            try:
                result = await self.channel.send(message)
                # Extract the result part for JSON-RPC response
                if isinstance(result, dict) and "result" in result:
                    return result["result"]
                elif isinstance(result, dict) and "error" in result:
                    error = result["error"]
                    raise MCPError(error)
                else:
                    return result
            except Exception as e:
                if isinstance(e, MCPError):
                    raise
                raise MCPError({"code": -1, "message": f"Failed to list resources: {e}"})
        else:
            # Handle other transports with request/response correlation
            future = asyncio.Future()
            self.pending_requests[request_id] = future

            try:
                await self.channel.send(message)
                result = await asyncio.wait_for(future, timeout=10.0)
                return result
            finally:
                self.pending_requests.pop(request_id, None)

    async def list_prompts(self) -> Dict[str, Any]:
        """List available prompts from MCP server."""
        # Auto-start if not already started
        if not self._started:
            await self.start()

        if not self.channel:
            raise ConnectionError(f"MCP server {self.name} failed to start")

        request_id = str(uuid.uuid4())
        message = MCPMessage(
            id=request_id,
            method="prompts/list",
            params={}
        )

        # Handle HTTP channels differently (immediate response)
        if hasattr(self.channel, 'send') and 'HTTP' in str(type(self.channel)):
            try:
                result = await self.channel.send(message)
                # Extract the result part for JSON-RPC response
                if isinstance(result, dict) and "result" in result:
                    return result["result"]
                elif isinstance(result, dict) and "error" in result:
                    error = result["error"]
                    raise MCPError(error)
                else:
                    return result
            except Exception as e:
                if isinstance(e, MCPError):
                    raise
                raise MCPError({"code": -1, "message": f"Failed to list prompts: {e}"})
        else:
            # Handle other transports with request/response correlation
            future = asyncio.Future()
            self.pending_requests[request_id] = future

            try:
                await self.channel.send(message)
                result = await asyncio.wait_for(future, timeout=10.0)
                return result
            finally:
                self.pending_requests.pop(request_id, None)

    async def _fetch_capabilities(self) -> None:
        """Fetch and cache server capabilities (tools, resources, prompts)."""
        if self._capabilities_fetched:
            return

        log.info(f"[MCPServer] Fetching capabilities for {self.name}")

        try:
            capabilities = {}

            # Add a small delay to ensure the connection is stable
            await asyncio.sleep(0.5)

            # Fetch tools with detailed error handling
            try:
                log.debug(f"[MCPServer] Fetching tools from {self.name}")
                tools_result = await self.list_tools()
                capabilities["tools"] = tools_result.get("tools", [])
                log.info(f"[MCPServer] Found {len(capabilities['tools'])} tools for {self.name}")

                # Log tool names for debugging
                if capabilities["tools"]:
                    tool_names = [tool.get("name", "unnamed") for tool in capabilities["tools"]]
                    log.debug(f"[MCPServer] Tool names: {tool_names}")

            except Exception as e:
                log.error(f"[MCPServer] Failed to fetch tools from {self.name}: {e}")
                log.debug(f"[MCPServer] Tool fetch error details: {type(e).__name__}: {str(e)}")
                capabilities["tools"] = []

            # Fetch resources with detailed error handling
            try:
                log.debug(f"[MCPServer] Fetching resources from {self.name}")
                resources_result = await self.list_resources()
                capabilities["resources"] = resources_result.get("resources", [])
                log.info(f"[MCPServer] Found {len(capabilities['resources'])} resources for {self.name}")
            except Exception as e:
                log.error(f"[MCPServer] Failed to fetch resources from {self.name}: {e}")
                log.debug(f"[MCPServer] Resource fetch error details: {type(e).__name__}: {str(e)}")
                capabilities["resources"] = []

            # Fetch prompts with detailed error handling
            try:
                log.debug(f"[MCPServer] Fetching prompts from {self.name}")
                prompts_result = await self.list_prompts()
                capabilities["prompts"] = prompts_result.get("prompts", [])
                log.info(f"[MCPServer] Found {len(capabilities['prompts'])} prompts for {self.name}")
            except Exception as e:
                log.error(f"[MCPServer] Failed to fetch prompts from {self.name}: {e}")
                log.debug(f"[MCPServer] Prompt fetch error details: {type(e).__name__}: {str(e)}")
                capabilities["prompts"] = []

            self._capabilities = capabilities
            self._capabilities_fetched = True

            total_capabilities = len(capabilities['tools']) + len(capabilities['resources']) + len(capabilities['prompts'])
            log.info(f"[MCPServer] Capabilities cached for {self.name}: "
                    f"{len(capabilities['tools'])} tools, "
                    f"{len(capabilities['resources'])} resources, "
                    f"{len(capabilities['prompts'])} prompts "
                    f"(total: {total_capabilities})")

        except Exception as e:
            log.error(f"[MCPServer] Critical error fetching capabilities for {self.name}: {e}")
            log.debug(f"[MCPServer] Critical error details: {type(e).__name__}: {str(e)}")
            # Set empty capabilities to avoid repeated failures
            self._capabilities = {"tools": [], "resources": [], "prompts": []}
            self._capabilities_fetched = True

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools with descriptions."""
        if self._capabilities:
            return self._capabilities.get("tools", [])
        return []

    def get_available_resources(self) -> List[Dict[str, Any]]:
        """Get list of available resources."""
        if self._capabilities:
            return self._capabilities.get("resources", [])
        return []

    def get_available_prompts(self) -> List[Dict[str, Any]]:
        """Get list of available prompts."""
        if self._capabilities:
            return self._capabilities.get("prompts", [])
        return []

    async def refresh_capabilities(self) -> None:
        """Manually refresh server capabilities."""
        log.info(f"[MCPServer] Manually refreshing capabilities for {self.name}")
        self._capabilities_fetched = False
        self._capabilities = None
        await self._fetch_capabilities()

    # Message handling
    async def _message_listener(self) -> None:
        """Listen for incoming MCP messages and handle them."""
        log.debug(f"[MCPServer] Starting message listener for {self.name}")

        try:
            async for message in self.channel.listen():
                await self._handle_message(message)

        except Exception as e:
            if self._started:  # Only log if we're supposed to be running
                log.error(f"[MCPServer] Message listener error for {self.name}: {e}")

        log.debug(f"[MCPServer] Message listener stopped for {self.name}")

    async def _handle_message(self, message: MCPMessage) -> None:
        """Handle incoming MCP message."""
        try:
            if message.is_response and message.id in self.pending_requests:
                # Handle response to our request
                await self._handle_response(message)

            elif message.is_notification:
                # Handle server notification
                await self._handle_notification(message)

            else:
                log.debug(f"[MCPServer] Ignoring message type from {self.name}: {message.method}")

        except Exception as e:
            log.error(f"[MCPServer] Error handling message from {self.name}: {e}")

    async def _handle_response(self, message: MCPMessage) -> None:
        """Handle response message and resolve pending request."""
        future = self.pending_requests.get(message.id)
        if not future or future.done():
            log.warning(f"[MCPServer] No pending request for response {message.id}")
            return

        try:
            if message.error:
                # Response contains error
                error = MCPError(message.error)
                future.set_exception(error)
                log.debug(f"[MCPServer] Request {message.id} failed: {error.message}")
            else:
                # Successful response
                future.set_result(message.result)
                log.debug(f"[MCPServer] Request {message.id} completed successfully")

        except Exception as e:
            future.set_exception(e)
            log.error(f"[MCPServer] Error processing response {message.id}: {e}")

    async def _handle_notification(self, message: MCPMessage) -> None:
        """Convert MCP notifications to framework events."""
        # Map MCP notifications to framework events
        event_mappings = {
            "tool/progress": "tool.progress",
            "resource/updated": "resource.changed",
            "server/status": "mcp.status",
            "notifications/cancelled": "mcp.cancelled"
        }

        event_type = event_mappings.get(message.method)
        if event_type:
            log.debug(f"[MCPServer] Converting notification {message.method} to {event_type}")

            # Emit framework event via the component's event system
            if hasattr(self, 'emit'):
                await self.emit(event_type, message.params)
            else:
                log.warning(f"[MCPServer] No emit method available for event {event_type}")

        else:
            log.debug(f"[MCPServer] Unknown notification type: {message.method}")

    def _get_framework_event_type(self, mcp_method: str) -> str:
        """Get framework event type for MCP method (for testing)."""
        event_mappings = {
            "tool/progress": "tool.progress",
            "resource/updated": "resource.changed",
            "server/status": "mcp.status",
            "notifications/cancelled": "mcp.cancelled"
        }
        return event_mappings.get(mcp_method, f"mcp.{mcp_method.replace('/', '.')}")

    # Health and status
    async def ping(self) -> bool:
        """Ping MCP server to check health."""
        # Auto-start if not already started
        if not self._started:
            try:
                await self.start()
            except Exception:
                return False

        if not self.channel:
            return False

        try:
            request_id = str(uuid.uuid4())
            message = MCPMessage(
                id=request_id,
                method="ping",
                params={}
            )

            future = asyncio.Future()
            self.pending_requests[request_id] = future

            await self.channel.send(message)
            await asyncio.wait_for(future, timeout=5.0)
            return True

        except Exception as e:
            log.warning(f"[MCPServer] Ping failed for {self.name}: {e}")
            return False

        finally:
            self.pending_requests.pop(request_id, None)

    def get_detailed_capabilities(self) -> Dict[str, Any]:
        """Get detailed information about server capabilities."""
        if not self._capabilities:
            return {"status": "capabilities not loaded"}

        details = {
            "tools": [],
            "resources": [],
            "prompts": []
        }

        # Detailed tool information
        for tool in self._capabilities.get("tools", []):
            tool_info = {
                "name": tool.get("name", "unknown"),
                "description": tool.get("description", "No description available")
            }
            if "inputSchema" in tool:
                schema = tool["inputSchema"]
                if "properties" in schema:
                    tool_info["parameters"] = list(schema["properties"].keys())
            details["tools"].append(tool_info)

        # Detailed resource information
        for resource in self._capabilities.get("resources", []):
            resource_info = {
                "uri": resource.get("uri", "unknown"),
                "name": resource.get("name", "unknown"),
                "description": resource.get("description", "No description available"),
                "mimeType": resource.get("mimeType", "unknown")
            }
            details["resources"].append(resource_info)

        # Detailed prompt information
        for prompt in self._capabilities.get("prompts", []):
            prompt_info = {
                "name": prompt.get("name", "unknown"),
                "description": prompt.get("description", "No description available")
            }
            if "arguments" in prompt:
                prompt_info["arguments"] = [arg.get("name", "unknown") for arg in prompt["arguments"]]
            details["prompts"].append(prompt_info)

        return details

    def get_tool_help(self, tool_name: str) -> str:
        """Get detailed help for a specific tool."""
        if not self._capabilities:
            return f"Tool '{tool_name}': Capabilities not loaded"

        for tool in self._capabilities.get("tools", []):
            if tool.get("name") == tool_name:
                help_text = f"Tool: {tool_name}\n"
                help_text += f"Description: {tool.get('description', 'No description available')}\n"

                if "inputSchema" in tool:
                    schema = tool["inputSchema"]
                    if "properties" in schema:
                        help_text += "Parameters:\n"
                        for param_name, param_info in schema["properties"].items():
                            param_desc = param_info.get("description", "No description")
                            param_type = param_info.get("type", "unknown")
                            required = param_name in schema.get("required", [])
                            required_text = " (required)" if required else " (optional)"
                            help_text += f"  - {param_name} ({param_type}){required_text}: {param_desc}\n"

                return help_text.strip()

        return f"Tool '{tool_name}' not found"

    def get_status(self) -> Dict[str, Any]:
        """Get component status information."""
        status = {
            "name": self.name,
            "server": self.server_name,
            "version": self.server_version,
            "started": self._started,
            "initialized": self._initialized,
            "connected": self.channel is not None,
            "pending_requests": len(self.pending_requests),
            "transport": self.metadata.get_preferred_transport().value if self.metadata else None,
            "description": self.description,
            "capabilities_loaded": self._capabilities_fetched
        }

        # Add capability counts if available
        if self._capabilities:
            status["capabilities"] = {
                "tools": len(self._capabilities.get("tools", [])),
                "resources": len(self._capabilities.get("resources", [])),
                "prompts": len(self._capabilities.get("prompts", []))
            }

        return status