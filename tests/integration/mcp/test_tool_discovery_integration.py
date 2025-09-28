#!/usr/bin/env python3
"""
Integration tests for the complete tool discovery fix.

Tests the end-to-end scenario where LLM agents build tool documentation
and MCP servers provide detailed capabilities instead of generic loading messages.
This verifies the complete fix for the tool discovery timing issue.
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
import logging

from woodwork.core.async_runtime import AsyncRuntime
from woodwork.components.mcp.mcp_server import MCPServer


class TestToolDiscoveryIntegration:
    """Integration tests for tool discovery fix."""

    @pytest.fixture
    def mock_github_mcp_server(self):
        """Create a mock GitHub MCP server for testing."""
        server = MCPServer(
            name="github_mcp",
            server="github/mcp-server",
            version="latest",
            env={"GITHUB_TOKEN": "test-token"}
        )

        # Mock successful GitHub server behavior
        async def mock_start():
            await asyncio.sleep(0.1)  # Simulate startup time
            server._started = True
            server._initialized = True
            server.metadata = Mock()
            server.metadata.description = "GitHub MCP Server - Interact with GitHub repositories"

        async def mock_fetch_capabilities():
            await asyncio.sleep(0.1)  # Simulate capability fetching
            server._capabilities = {
                "tools": [
                    {"name": "get_issue", "description": "Get details about a GitHub issue"},
                    {"name": "create_pull_request", "description": "Create a new pull request"},
                    {"name": "list_repositories", "description": "List repositories for a user/organization"},
                    {"name": "create_issue", "description": "Create a new GitHub issue"},
                    {"name": "get_user", "description": "Get user profile information"}
                ],
                "resources": [
                    {"name": "repository", "description": "Repository data access"}
                ],
                "prompts": []
            }
            server._capabilities_fetched = True

        server.start = mock_start
        server._fetch_capabilities = mock_fetch_capabilities

        return server

    @pytest.fixture
    def mock_llm_agent(self):
        """Create a mock LLM agent that simulates tool documentation building."""
        class MockLLMAgent:
            def __init__(self, name="test_agent"):
                self.name = name
                self.type = "agent"
                self._tools = []

            def set_tools(self, tools):
                """Set the tools available to this agent."""
                self._tools = tools

            def build_tool_documentation(self):
                """Simulate the LLM agent building tool documentation."""
                tool_documentation = ""
                for obj in self._tools:
                    tool_documentation += f"tool name: {obj.name}\n"
                    tool_documentation += f"tool type: {obj.type}\n"
                    tool_documentation += f"<tool_description>\n{obj.description}</tool_description>\n\n\n"
                return tool_documentation

            def simulate_llm_context_building(self):
                """Simulate how the LLM builds its context with available tools."""
                context = "Here are the available tools:\n"
                context += self.build_tool_documentation()
                context += "\nYou are a reasoning agent that solves user prompts step-by-step using available tools."
                return context

        return MockLLMAgent()

    @pytest.mark.asyncio
    async def test_tool_discovery_issue_reproduction_and_fix(self, mock_github_mcp_server, mock_llm_agent):
        """
        Test that reproduces the original tool discovery issue and verifies the fix.

        This test simulates the complete flow:
        1. Components are created
        2. LLM agent builds tool documentation
        3. Verifies that detailed capabilities are available instead of loading messages
        """

        # Set up the agent with the MCP server
        mock_llm_agent.set_tools([mock_github_mcp_server])

        # 1. Test the BEFORE scenario (what would happen without the fix)
        print("Testing BEFORE fix scenario...")

        # Before any startup, the server should show initializing message
        description_before_startup = mock_github_mcp_server.description
        tools_before_startup = mock_github_mcp_server.get_available_tools()

        assert "initializing for tool discovery" in description_before_startup
        assert len(tools_before_startup) == 0

        print(f"BEFORE: {description_before_startup}")
        print(f"BEFORE tools: {len(tools_before_startup)}")

        # 2. Test the AFTER scenario (with the AsyncRuntime fix)
        print("\nTesting AFTER fix scenario...")

        # Create AsyncRuntime and go through proper startup sequence
        runtime = AsyncRuntime()
        config = {
            "components": [mock_github_mcp_server, mock_llm_agent]
        }

        # Initialize components
        await runtime.initialize_components(config)

        # The key fix: wait for async component startup
        await runtime.startup_async_components()

        # Now test tool discovery
        description_after_startup = mock_github_mcp_server.description
        tools_after_startup = mock_github_mcp_server.get_available_tools()

        print(f"AFTER: {description_after_startup}")
        print(f"AFTER tools: {len(tools_after_startup)}")

        # 3. Verify the fix works
        assert "GitHub MCP Server - Interact with GitHub repositories" in description_after_startup
        assert "Tools:" in description_after_startup
        assert "get_issue" in description_after_startup
        assert len(tools_after_startup) == 5

        # 4. Test LLM agent tool documentation building
        tool_documentation = mock_llm_agent.build_tool_documentation()
        llm_context = mock_llm_agent.simulate_llm_context_building()

        print(f"\nLLM Tool Documentation:\n{tool_documentation[:300]}...")

        # Verify LLM sees detailed tool information
        assert "GitHub MCP Server - Interact with GitHub repositories" in tool_documentation
        assert "Tools:" in tool_documentation
        assert "get_issue" in tool_documentation
        assert "create_pull_request" in tool_documentation

        # Verify LLM context includes proper tool information
        assert "GitHub MCP Server" in llm_context
        assert "get_issue" in llm_context
        assert "Here are the available tools:" in llm_context

        await runtime._cleanup()

    @pytest.mark.asyncio
    async def test_multiple_mcp_servers_startup(self):
        """Test that multiple MCP servers all complete startup before LLM context building."""
        # Create multiple MCP servers
        servers = []
        for i in range(3):
            server = MCPServer(
                name=f"mcp_server_{i}",
                server=f"test/server_{i}",
                version="1.0"
            )

            # Mock each server with different startup times
            startup_delay = 0.1 * (i + 1)  # 0.1s, 0.2s, 0.3s

            async def make_mock_start(delay, srv):
                async def mock_start():
                    await asyncio.sleep(delay)
                    srv._started = True
                    srv.metadata = Mock()
                    srv.metadata.description = f"Test Server {srv.name[-1]}"
                return mock_start

            async def make_mock_fetch(delay, srv):
                async def mock_fetch():
                    await asyncio.sleep(delay)
                    srv._capabilities = {
                        "tools": [{"name": f"tool_{srv.name[-1]}", "description": f"Tool for server {srv.name[-1]}"}]
                    }
                    srv._capabilities_fetched = True
                return mock_fetch

            server.start = await make_mock_start(startup_delay, server)
            server._fetch_capabilities = await make_mock_fetch(startup_delay, server)
            servers.append(server)

        # Create runtime and start all servers
        runtime = AsyncRuntime()
        config = {"components": servers}

        await runtime.initialize_components(config)

        # All servers should start in parallel
        import time
        start_time = time.time()
        await runtime.startup_async_components()
        end_time = time.time()

        # Should complete in about 0.3s (longest server) + some overhead, not 0.6s (sequential)
        assert end_time - start_time < 0.5, "Servers should start in parallel"

        # All servers should be started and have capabilities
        for i, server in enumerate(servers):
            assert server._started, f"Server {i} should be started"
            assert server._capabilities_fetched, f"Server {i} should have capabilities"

            # Descriptions should show tool information
            description = server.description
            assert f"Test Server {i}" in description
            assert f"tool_{i}" in description

        await runtime._cleanup()

    @pytest.mark.asyncio
    async def test_tool_discovery_with_failing_server(self, mock_github_mcp_server):
        """Test that tool discovery works even when some servers fail to start."""
        # Create a server that fails to start
        failing_server = MCPServer(
            name="failing_mcp",
            server="failing/server",
            version="1.0"
        )

        async def failing_start():
            await asyncio.sleep(0.1)
            raise RuntimeError("Server failed to start")

        failing_server.start = failing_start

        # Set up runtime with both successful and failing servers
        runtime = AsyncRuntime()
        config = {"components": [mock_github_mcp_server, failing_server]}

        await runtime.initialize_components(config)

        # Should handle the failure gracefully
        await runtime.startup_async_components()

        # Successful server should work normally
        assert mock_github_mcp_server._started
        assert mock_github_mcp_server._capabilities_fetched

        description = mock_github_mcp_server.description
        assert "GitHub MCP Server" in description

        # Failing server should show appropriate status
        failing_description = failing_server.description
        assert "failing/server" in failing_description

        await runtime._cleanup()

    @pytest.mark.asyncio
    async def test_end_to_end_timing_verification(self, mock_github_mcp_server, mock_llm_agent):
        """Test that verifies the timing fix - tools are available when LLM needs them."""

        mock_llm_agent.set_tools([mock_github_mcp_server])

        # Simulate the old problematic flow (without AsyncRuntime startup)
        old_flow_description = mock_github_mcp_server.description
        old_flow_tools = len(mock_github_mcp_server.get_available_tools())
        old_flow_documentation = mock_llm_agent.build_tool_documentation()

        # Should show loading state in old flow
        assert "initializing for tool discovery" in old_flow_description
        assert old_flow_tools == 0
        assert "initializing for tool discovery" in old_flow_documentation

        # Simulate the new fixed flow (with AsyncRuntime startup)
        runtime = AsyncRuntime()
        config = {"components": [mock_github_mcp_server, mock_llm_agent]}

        await runtime.initialize_components(config)
        await runtime.startup_async_components()  # This is the key fix

        new_flow_description = mock_github_mcp_server.description
        new_flow_tools = len(mock_github_mcp_server.get_available_tools())
        new_flow_documentation = mock_llm_agent.build_tool_documentation()

        # Should show detailed capabilities in new flow
        assert "GitHub MCP Server" in new_flow_description
        assert "Tools:" in new_flow_description
        assert new_flow_tools == 5
        assert "GitHub MCP Server" in new_flow_documentation
        assert "get_issue" in new_flow_documentation

        # Verify the improvement
        assert old_flow_description != new_flow_description
        assert old_flow_tools < new_flow_tools
        assert "initializing" in old_flow_documentation and "get_issue" in new_flow_documentation

        await runtime._cleanup()

    @pytest.mark.asyncio
    async def test_performance_impact_of_blocking_startup(self):
        """Test that blocking startup doesn't significantly impact performance."""
        # Create several fast-starting servers
        servers = []
        for i in range(5):
            server = MCPServer(
                name=f"fast_server_{i}",
                server=f"fast/server_{i}",
                version="1.0"
            )

            async def quick_start(srv):
                await asyncio.sleep(0.01)  # Very fast startup
                srv._started = True
                srv._capabilities_fetched = True
                srv._capabilities = {"tools": []}

            server.start = lambda s=server: quick_start(s)
            server._fetch_capabilities = AsyncMock()
            servers.append(server)

        runtime = AsyncRuntime()
        config = {"components": servers}

        await runtime.initialize_components(config)

        # Measure startup time
        import time
        start_time = time.time()
        await runtime.startup_async_components()
        end_time = time.time()

        # Should complete quickly even with multiple servers
        assert end_time - start_time < 1.0, "Startup should be fast for quick-starting servers"

        # All servers should be ready
        for server in servers:
            assert server._started
            assert server._capabilities_fetched

        await runtime._cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])