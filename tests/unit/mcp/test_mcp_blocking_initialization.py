#!/usr/bin/env python3
"""
Unit tests for MCP server blocking initialization mechanism.

Tests the blocking initialization features added to resolve tool discovery
timing issues where LLM agents need immediate access to tool capabilities.
"""

import asyncio
import pytest
import time
from unittest.mock import Mock, AsyncMock, patch
import logging

from woodwork.components.mcp.mcp_server import MCPServer


class TestMCPServerBlockingInitialization:
    """Test MCP server blocking initialization behavior."""

    @pytest.fixture
    def basic_mcp_server(self):
        """Create a basic MCP server for testing."""
        with patch('woodwork.components.mcp.mcp_server.asyncio.get_running_loop'):
            server = MCPServer(
                name="test_mcp",
                server="test/server",
                version="1.0",
                env={"TEST_TOKEN": "test-value"}
            )
        return server

    def test_mcp_server_initializes_blocking_startup_task_attribute(self, basic_mcp_server):
        """Test that MCP server initializes the blocking startup task attribute."""
        assert hasattr(basic_mcp_server, '_blocking_startup_task')
        # Initially None until event loop is available
        assert basic_mcp_server._blocking_startup_task is None

    @pytest.mark.asyncio
    async def test_trigger_blocking_initialization_creates_task(self):
        """Test that _trigger_blocking_initialization creates a background task."""
        server = MCPServer(
            name="test_mcp",
            server="test/server",
            version="1.0"
        )

        # Should have created the blocking startup task
        assert hasattr(server, '_blocking_startup_task')
        assert server._blocking_startup_task is not None
        assert isinstance(server._blocking_startup_task, asyncio.Task)

    @pytest.mark.asyncio
    async def test_blocking_startup_sequence_successful_flow(self):
        """Test the complete blocking startup sequence with successful execution."""
        server = MCPServer(
            name="test_mcp",
            server="test/server",
            version="1.0"
        )

        # Mock the external dependencies
        startup_call_order = []

        async def mock_start():
            startup_call_order.append("start")
            await asyncio.sleep(0.1)  # Simulate startup time
            server._started = True
            server.metadata = Mock()
            server.metadata.description = "Test MCP Server"

        async def mock_fetch_capabilities():
            startup_call_order.append("fetch_capabilities")
            await asyncio.sleep(0.1)  # Simulate capability fetching
            server._capabilities = {
                "tools": [
                    {"name": "test_tool_1", "description": "First test tool"},
                    {"name": "test_tool_2", "description": "Second test tool"}
                ],
                "resources": [],
                "prompts": []
            }
            server._capabilities_fetched = True

        server.start = mock_start
        server._fetch_capabilities = mock_fetch_capabilities

        # Record start time
        start_time = time.time()

        # Execute blocking startup sequence
        await server._blocking_startup_sequence()

        # Record end time
        end_time = time.time()

        # Verify the sequence completed properly
        assert server._started, "Server should be marked as started"
        assert server._capabilities_fetched, "Capabilities should be fetched"
        assert len(server._capabilities["tools"]) == 2, "Should have 2 tools"

        # Verify methods were called in correct order
        assert startup_call_order == ["start", "fetch_capabilities"]

        # Should have taken some time (at least 0.2s due to sleep calls)
        assert end_time - start_time >= 0.2, "Blocking startup should wait for completion"

    @pytest.mark.asyncio
    async def test_blocking_startup_sequence_with_already_started_server(self):
        """Test blocking startup when server is already started."""
        server = MCPServer(
            name="test_mcp",
            server="test/server",
            version="1.0"
        )

        # Mark server as already started
        server._started = True

        # Mock methods (should not be called)
        server.start = AsyncMock()
        server._fetch_capabilities = AsyncMock()

        # Execute blocking startup sequence
        await server._blocking_startup_sequence()

        # Verify methods were not called since server was already started
        server.start.assert_not_called()
        server._fetch_capabilities.assert_not_called()

    @pytest.mark.asyncio
    async def test_blocking_startup_sequence_handles_start_failure(self):
        """Test that blocking startup handles server start failures gracefully."""
        server = MCPServer(
            name="test_mcp",
            server="test/server",
            version="1.0"
        )

        # Mock start method that raises an exception
        async def failing_start():
            raise RuntimeError("Server failed to start")

        server.start = failing_start

        # Should not raise exception, should handle gracefully
        await server._blocking_startup_sequence()

        # Server should not be marked as started
        assert not server._started
        assert not server._capabilities_fetched

    @pytest.mark.asyncio
    async def test_blocking_startup_sequence_handles_capability_fetch_failure(self):
        """Test that blocking startup handles capability fetch failures gracefully."""
        server = MCPServer(
            name="test_mcp",
            server="test/server",
            version="1.0"
        )

        # Mock successful start but failing capability fetch
        async def mock_start():
            server._started = True

        async def failing_fetch():
            raise ConnectionError("Failed to fetch capabilities")

        server.start = mock_start
        server._fetch_capabilities = failing_fetch

        # Should not raise exception
        await server._blocking_startup_sequence()

        # Server started but capabilities not fetched
        assert server._started
        assert not server._capabilities_fetched

    @pytest.mark.asyncio
    async def test_blocking_startup_sequence_timeout_handling(self):
        """Test that blocking startup handles slow capability fetching with timeout."""
        server = MCPServer(
            name="test_mcp",
            server="test/server",
            version="1.0"
        )

        # Mock fast start but very slow capability fetch
        async def quick_start():
            server._started = True

        async def slow_fetch():
            await asyncio.sleep(6)  # Longer than 5 second timeout
            server._capabilities_fetched = True

        server.start = quick_start
        server._fetch_capabilities = slow_fetch

        start_time = time.time()
        await server._blocking_startup_sequence()
        end_time = time.time()

        # Should complete in reasonable time (not wait full 6 seconds)
        assert end_time - start_time < 6, "Should timeout before slow fetch completes"
        assert server._started, "Server should be started"
        assert not server._capabilities_fetched, "Capabilities should not be fetched due to timeout"

    @pytest.mark.asyncio
    async def test_wait_for_capabilities_with_existing_capabilities(self):
        """Test _wait_for_capabilities when capabilities are already loaded."""
        server = MCPServer(
            name="test_mcp",
            server="test/server",
            version="1.0"
        )

        # Mark capabilities as already fetched
        server._capabilities_fetched = True

        # Should return immediately
        start_time = time.time()
        result = await server._wait_for_capabilities(timeout=5.0)
        end_time = time.time()

        assert result is True
        assert end_time - start_time < 0.1, "Should return immediately when capabilities exist"

    @pytest.mark.asyncio
    async def test_wait_for_capabilities_with_blocking_task(self):
        """Test _wait_for_capabilities waits for blocking startup task."""
        server = MCPServer(
            name="test_mcp",
            server="test/server",
            version="1.0"
        )

        # Create a blocking startup task that completes successfully
        async def mock_blocking_task():
            await asyncio.sleep(0.2)
            server._capabilities_fetched = True

        server._blocking_startup_task = asyncio.create_task(mock_blocking_task())

        start_time = time.time()
        result = await server._wait_for_capabilities(timeout=1.0)
        end_time = time.time()

        assert result is True
        assert server._capabilities_fetched
        assert end_time - start_time >= 0.2, "Should wait for blocking task to complete"

    @pytest.mark.asyncio
    async def test_wait_for_capabilities_timeout(self):
        """Test _wait_for_capabilities handles timeout correctly."""
        server = MCPServer(
            name="test_mcp",
            server="test/server",
            version="1.0"
        )

        # Create a blocking startup task that takes too long
        async def slow_blocking_task():
            await asyncio.sleep(2.0)
            server._capabilities_fetched = True

        server._blocking_startup_task = asyncio.create_task(slow_blocking_task())

        start_time = time.time()
        result = await server._wait_for_capabilities(timeout=0.5)
        end_time = time.time()

        assert result is False
        assert not server._capabilities_fetched
        assert end_time - start_time >= 0.5, "Should wait for timeout period"
        assert end_time - start_time < 1.0, "Should not wait longer than timeout"


class TestMCPServerDescriptionWithBlocking:
    """Test MCP server description property with blocking initialization."""

    def test_description_property_shows_initializing_status(self):
        """Test that description shows initializing status during startup."""
        with patch('woodwork.components.mcp.mcp_server.asyncio.get_running_loop'):
            server = MCPServer(
                name="test_mcp",
                server="github/mcp-server",
                version="latest"
            )

        description = server.description

        # Should indicate initialization is happening
        assert "initializing for tool discovery" in description
        assert "github/mcp-server:latest" in description

    def test_description_property_with_completed_capabilities(self):
        """Test description property when capabilities are fully loaded."""
        with patch('woodwork.components.mcp.mcp_server.asyncio.get_running_loop'):
            server = MCPServer(
                name="test_mcp",
                server="github/mcp-server",
                version="latest"
            )

        # Mock completed state
        server._started = True
        server._capabilities_fetched = True
        server.metadata = Mock()
        server.metadata.description = "GitHub MCP Server - Interact with repositories"
        server._capabilities = {
            "tools": [
                {"name": "get_issue", "description": "Get GitHub issue by number"},
                {"name": "create_pull_request", "description": "Create new PR"},
                {"name": "list_repositories", "description": "List user repositories"}
            ],
            "resources": [
                {"name": "repository", "description": "Repository resource"}
            ],
            "prompts": []
        }

        description = server.description

        # Should show detailed information
        assert "GitHub MCP Server - Interact with repositories" in description
        assert "Tools: get_issue, create_pull_request, list_repositories" in description
        assert "Resources: 1 available" in description

    def test_description_property_waits_for_blocking_startup(self):
        """Test that description property attempts to wait for blocking startup."""
        server = MCPServer(
            name="test_mcp",
            server="test/server",
            version="1.0"
        )

        # Create a mock blocking startup task
        startup_completed = False

        async def mock_startup_task():
            nonlocal startup_completed
            await asyncio.sleep(0.1)
            startup_completed = True
            server._capabilities_fetched = True
            server.metadata = Mock()
            server.metadata.description = "Test Server"
            server._capabilities = {"tools": []}

        server._blocking_startup_task = asyncio.create_task(mock_startup_task())

        # Access description property - should attempt to wait briefly
        # Note: This is synchronous so it uses time.sleep, not asyncio.sleep
        with patch('time.sleep') as mock_sleep:
            description = server.description

            # Should have attempted to wait
            mock_sleep.assert_called()


class TestBlockingInitializationEdgeCases:
    """Test edge cases and error conditions for blocking initialization."""

    @pytest.mark.asyncio
    async def test_blocking_initialization_without_event_loop(self):
        """Test blocking initialization when no event loop is available."""
        # Create server without event loop context
        with patch('asyncio.get_running_loop', side_effect=RuntimeError("No event loop")):
            server = MCPServer(
                name="test_mcp",
                server="test/server",
                version="1.0"
            )

        # Should not have blocking startup task
        assert server._blocking_startup_task is None

    def test_blocking_initialization_trigger_with_exception(self):
        """Test that _trigger_blocking_initialization handles exceptions gracefully."""
        with patch('asyncio.get_running_loop', side_effect=Exception("Unexpected error")):
            # Should not raise exception during initialization
            server = MCPServer(
                name="test_mcp",
                server="test/server",
                version="1.0"
            )

        # Should handle exception gracefully
        assert hasattr(server, '_blocking_startup_task')

    @pytest.mark.asyncio
    async def test_multiple_blocking_startup_calls(self):
        """Test that multiple calls to blocking startup sequence are handled safely."""
        server = MCPServer(
            name="test_mcp",
            server="test/server",
            version="1.0"
        )

        start_call_count = 0

        async def counting_start():
            nonlocal start_call_count
            start_call_count += 1
            server._started = True

        server.start = counting_start
        server._fetch_capabilities = AsyncMock()

        # Call blocking startup multiple times
        await server._blocking_startup_sequence()
        await server._blocking_startup_sequence()
        await server._blocking_startup_sequence()

        # Start should only be called once (subsequent calls see _started = True)
        assert start_call_count == 1

    @pytest.mark.asyncio
    async def test_blocking_startup_with_partial_success(self):
        """Test blocking startup when server starts but capability fetch partially fails."""
        server = MCPServer(
            name="test_mcp",
            server="test/server",
            version="1.0"
        )

        # Mock successful start but partial capability fetch
        async def mock_start():
            server._started = True

        async def partial_fetch():
            # Simulate partial success - server starts but some capabilities fail
            server._capabilities = {"tools": []}  # Empty but valid
            server._capabilities_fetched = True

        server.start = mock_start
        server._fetch_capabilities = partial_fetch

        await server._blocking_startup_sequence()

        # Should handle partial success gracefully
        assert server._started
        assert server._capabilities_fetched
        assert server._capabilities == {"tools": []}


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])