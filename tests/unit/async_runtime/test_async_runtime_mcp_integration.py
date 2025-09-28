#!/usr/bin/env python3
"""
Unit tests for AsyncRuntime MCP server integration and blocking initialization.

Tests the fix for tool discovery timing issues where MCP servers need to complete
async initialization before LLM agents access their descriptions.
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
import logging

from woodwork.core.async_runtime import AsyncRuntime
from woodwork.components.mcp.mcp_server import MCPServer


class TestAsyncRuntimeMCPIntegration:
    """Test AsyncRuntime integration with MCP server blocking initialization."""

    @pytest.fixture
    def mock_mcp_server(self):
        """Create a mock MCP server for testing."""
        server = MCPServer(
            name="test_mcp",
            server="test/server",
            version="1.0",
            env={"TEST_TOKEN": "test-value"}
        )
        return server

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent that accesses tool descriptions."""
        class MockAgent:
            def __init__(self):
                self.name = "test_agent"
                self.type = "agent"
                self._tools = []

            def set_tools(self, tools):
                self._tools = tools

            def get_tool_documentation(self):
                """Simulate LLM agent building tool documentation."""
                tool_docs = ""
                for tool in self._tools:
                    tool_docs += f"tool name: {tool.name}\n"
                    tool_docs += f"tool type: {tool.type}\n"
                    tool_docs += f"<tool_description>\n{tool.description}</tool_description>\n\n"
                return tool_docs

        return MockAgent()

    @pytest.mark.asyncio
    async def test_startup_async_components_waits_for_mcp_server(self, mock_mcp_server):
        """Test that startup_async_components waits for MCP server blocking initialization."""
        # Setup mock for successful startup
        startup_completed = False

        async def mock_blocking_startup():
            await asyncio.sleep(0.1)  # Simulate startup delay
            mock_mcp_server._started = True
            mock_mcp_server._capabilities_fetched = True
            mock_mcp_server._capabilities = {
                "tools": [{"name": "test_tool", "description": "Test tool"}]
            }
            nonlocal startup_completed
            startup_completed = True

        # Set the blocking startup task
        mock_mcp_server._blocking_startup_task = asyncio.create_task(mock_blocking_startup())

        # Create runtime and config
        runtime = AsyncRuntime()
        config = {"components": [mock_mcp_server]}

        # Initialize components
        await runtime.initialize_components(config)

        # Verify startup hasn't completed yet
        assert not startup_completed
        assert not mock_mcp_server._capabilities_fetched

        # Start async components - this should wait for the blocking startup
        await runtime.startup_async_components()

        # Verify startup completed
        assert startup_completed
        assert mock_mcp_server._capabilities_fetched
        assert mock_mcp_server._started

        await runtime._cleanup()

    @pytest.mark.asyncio
    async def test_startup_async_components_handles_timeout(self, mock_mcp_server):
        """Test that startup_async_components handles slow-starting components gracefully."""
        # Setup mock for slow startup that times out
        async def slow_blocking_startup():
            await asyncio.sleep(35)  # Longer than 30s timeout
            mock_mcp_server._started = True

        mock_mcp_server._blocking_startup_task = asyncio.create_task(slow_blocking_startup())

        runtime = AsyncRuntime()
        config = {"components": [mock_mcp_server]}

        await runtime.initialize_components(config)

        # This should complete without hanging, even though the component times out
        await runtime.startup_async_components()

        # The component should not be marked as started due to timeout
        assert not mock_mcp_server._started

        await runtime._cleanup()

    @pytest.mark.asyncio
    async def test_startup_async_components_handles_exceptions(self, mock_mcp_server):
        """Test that startup_async_components handles component startup exceptions."""
        # Setup mock that raises an exception
        async def failing_startup():
            await asyncio.sleep(0.1)
            raise RuntimeError("Simulated startup failure")

        mock_mcp_server._blocking_startup_task = asyncio.create_task(failing_startup())

        runtime = AsyncRuntime()
        config = {"components": [mock_mcp_server]}

        await runtime.initialize_components(config)

        # This should complete without raising, handling the exception gracefully
        await runtime.startup_async_components()

        await runtime._cleanup()

    @pytest.mark.asyncio
    async def test_startup_async_components_with_mixed_components(self):
        """Test startup with mix of sync and async components."""
        # Create mock MCP server with async startup
        mcp_server = MCPServer(
            name="async_mcp",
            server="test/async",
            version="1.0"
        )

        async def mock_startup():
            await asyncio.sleep(0.1)
            mcp_server._started = True
            mcp_server._capabilities_fetched = True

        mcp_server._blocking_startup_task = asyncio.create_task(mock_startup())

        # Create mock sync component
        class SyncComponent:
            def __init__(self):
                self.name = "sync_comp"
                self.type = "sync"

        sync_comp = SyncComponent()

        runtime = AsyncRuntime()
        config = {"components": [mcp_server, sync_comp]}

        await runtime.initialize_components(config)

        # Should handle mixed components correctly
        await runtime.startup_async_components()

        # Verify async component started, sync component unaffected
        assert mcp_server._started
        assert hasattr(sync_comp, 'name')

        await runtime._cleanup()

    @pytest.mark.asyncio
    async def test_startup_async_components_no_async_components(self):
        """Test startup when no async components are present."""
        # Create only sync components
        class SyncComponent:
            def __init__(self, name):
                self.name = name
                self.type = "sync"

        components = [SyncComponent("comp1"), SyncComponent("comp2")]

        runtime = AsyncRuntime()
        config = {"components": components}

        await runtime.initialize_components(config)

        # Should complete quickly with no async components
        await runtime.startup_async_components()

        # All components should be registered
        assert len(runtime.components) == 2

        await runtime._cleanup()


class TestMCPServerBlockingInitialization:
    """Test MCP server blocking initialization behavior."""

    @pytest.mark.asyncio
    async def test_mcp_server_creates_blocking_startup_task(self):
        """Test that MCP server creates blocking startup task during initialization."""
        with patch.object(asyncio, 'get_running_loop', return_value=Mock()):
            server = MCPServer(
                name="test_server",
                server="test/server",
                version="1.0"
            )

            # Should have created a blocking startup task
            assert hasattr(server, '_blocking_startup_task')
            assert server._blocking_startup_task is not None

    @pytest.mark.asyncio
    async def test_blocking_startup_sequence_success(self):
        """Test successful blocking startup sequence."""
        server = MCPServer(
            name="test_server",
            server="test/server",
            version="1.0"
        )

        # Mock successful startup methods
        async def mock_start():
            server._started = True
            server.metadata = Mock()
            server.metadata.description = "Test Server"

        async def mock_fetch_capabilities():
            server._capabilities = {
                "tools": [{"name": "test_tool", "description": "Test"}]
            }
            server._capabilities_fetched = True

        server.start = mock_start
        server._fetch_capabilities = mock_fetch_capabilities

        # Run blocking startup sequence
        await server._blocking_startup_sequence()

        # Verify results
        assert server._started
        assert server._capabilities_fetched
        assert len(server._capabilities["tools"]) == 1

    @pytest.mark.asyncio
    async def test_blocking_startup_sequence_timeout(self):
        """Test blocking startup sequence with timeout."""
        server = MCPServer(
            name="test_server",
            server="test/server",
            version="1.0"
        )

        # Mock slow startup
        async def slow_start():
            await asyncio.sleep(0.1)
            server._started = True

        async def slow_fetch():
            await asyncio.sleep(6)  # Will timeout (longer than 5s timeout in blocking startup)
            server._capabilities_fetched = True

        server.start = slow_start
        server._fetch_capabilities = slow_fetch

        # Should complete without hanging
        await server._blocking_startup_sequence()

        # Started but capabilities not fetched due to timeout
        assert server._started
        assert not server._capabilities_fetched

    @pytest.mark.asyncio
    async def test_blocking_startup_sequence_handles_exceptions(self):
        """Test that blocking startup handles exceptions gracefully."""
        server = MCPServer(
            name="test_server",
            server="test/server",
            version="1.0"
        )

        # Mock failing startup
        async def failing_start():
            raise RuntimeError("Startup failed")

        server.start = failing_start

        # Should not raise exception
        await server._blocking_startup_sequence()

        # Should not be marked as started
        assert not server._started
        assert not server._capabilities_fetched


class TestMCPServerDescriptionIntegration:
    """Test MCP server description property with blocking initialization."""

    def test_description_before_startup(self):
        """Test description property before startup completes."""
        server = MCPServer(
            name="test_server",
            server="test/server",
            version="1.0"
        )

        description = server.description

        # Should show initializing status
        assert "initializing for tool discovery" in description
        assert server.server_name in description

    def test_description_after_successful_startup(self):
        """Test description property after successful startup."""
        server = MCPServer(
            name="test_server",
            server="test/server",
            version="1.0"
        )

        # Mock successful state
        server._started = True
        server._capabilities_fetched = True
        server.metadata = Mock()
        server.metadata.description = "GitHub MCP Server"
        server._capabilities = {
            "tools": [
                {"name": "get_issue", "description": "Get issue"},
                {"name": "create_pr", "description": "Create PR"}
            ],
            "resources": [{"name": "repo", "description": "Repository"}],
            "prompts": []
        }

        description = server.description

        # Should show detailed capabilities
        assert "GitHub MCP Server" in description
        assert "Tools:" in description
        assert "get_issue" in description
        assert "Resources:" in description

    def test_description_with_many_tools(self):
        """Test description property with many tools (should truncate)."""
        server = MCPServer(
            name="test_server",
            server="test/server",
            version="1.0"
        )

        # Mock state with many tools
        server._started = True
        server._capabilities_fetched = True
        server.metadata = Mock()
        server.metadata.description = "Test Server"
        server._capabilities = {
            "tools": [{"name": f"tool_{i}", "description": f"Tool {i}"} for i in range(10)],
            "resources": [],
            "prompts": []
        }

        description = server.description

        # Should show first 5 tools plus count
        assert "Tools:" in description
        assert "tool_0" in description
        assert "tool_4" in description
        assert "+5 more" in description


class TestEndToEndIntegration:
    """End-to-end integration tests for the complete flow."""

    @pytest.mark.asyncio
    async def test_complete_initialization_flow(self):
        """Test the complete flow from component creation to tool documentation."""
        # Create MCP server
        server = MCPServer(
            name="github_mcp",
            server="github/mcp-server",
            version="latest",
            env={"GITHUB_TOKEN": "test-token"}
        )

        # Mock successful capabilities
        async def mock_start():
            server._started = True
            server.metadata = Mock()
            server.metadata.description = "GitHub MCP Server"

        async def mock_fetch():
            server._capabilities = {
                "tools": [
                    {"name": "get_issue", "description": "Get GitHub issue"},
                    {"name": "create_pr", "description": "Create pull request"}
                ]
            }
            server._capabilities_fetched = True

        server.start = mock_start
        server._fetch_capabilities = mock_fetch

        # Create agent that builds tool documentation
        class TestAgent:
            def __init__(self):
                self.name = "test_agent"
                self.type = "agent"
                self._tools = []

            def set_tools(self, tools):
                self._tools = tools

            def build_documentation(self):
                return "\n".join(f"{tool.name}: {tool.description}" for tool in self._tools)

        agent = TestAgent()
        agent.set_tools([server])

        # Test the complete flow
        runtime = AsyncRuntime()
        config = {"components": [server, agent]}

        # 1. Initialize components
        await runtime.initialize_components(config)

        # 2. Before startup - should show loading
        description_before = server.description
        assert "initializing for tool discovery" in description_before

        # 3. Wait for async startup
        await runtime.startup_async_components()

        # 4. After startup - should show capabilities
        description_after = server.description
        assert "GitHub MCP Server" in description_after
        assert "Tools:" in description_after

        # 5. Agent should now see proper tool information
        documentation = agent.build_documentation()
        assert "github_mcp:" in documentation
        assert "GitHub MCP Server" in documentation

        await runtime._cleanup()

    @pytest.mark.asyncio
    async def test_integration_with_runtime_start_method(self):
        """Test integration with AsyncRuntime.start() method."""
        # Mock the config parsing to return our test components
        server = MCPServer(
            name="test_mcp",
            server="test/server",
            version="1.0"
        )

        # Mock successful startup
        async def mock_start():
            server._started = True
            server._capabilities_fetched = True
            server.metadata = Mock()
            server.metadata.description = "Test MCP Server"
            server._capabilities = {"tools": [{"name": "test", "description": "Test tool"}]}

        server.start = mock_start
        server._fetch_capabilities = AsyncMock()

        config = {"components": [server]}

        runtime = AsyncRuntime()

        # Mock the component parsing to avoid actual config parsing
        async def mock_parse_components(config_dict):
            return [server]

        with patch.object(runtime, '_parse_components', mock_parse_components):
            with patch.object(runtime, '_main_loop', AsyncMock()):  # Skip main loop
                with patch.object(runtime.event_bus, 'configure_routing'):
                    with patch.object(runtime, 'has_api_component', return_value=False):
                        # This should call startup_async_components as part of the flow
                        await runtime.start(config)

                        # Wait a bit for the mocked startup to complete
                        await asyncio.sleep(0.1)

                        # Verify server was started during runtime initialization
                        assert server._started
                        assert server._capabilities_fetched


if __name__ == "__main__":
    pytest.main([__file__, "-v"])