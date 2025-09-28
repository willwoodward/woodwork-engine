#!/usr/bin/env python3
"""
Unit tests for AsyncRuntime startup_async_components functionality.

Tests the AsyncRuntime enhancement that waits for async component startup
to complete before proceeding to the main loop, ensuring MCP servers and
other async components are ready before processing begins.
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
import logging

from woodwork.core.async_runtime import AsyncRuntime


class TestAsyncRuntimeStartupComponents:
    """Test AsyncRuntime startup_async_components method."""

    @pytest.fixture
    def runtime(self):
        """Create a basic AsyncRuntime for testing."""
        return AsyncRuntime()

    @pytest.fixture
    def mock_mcp_server_with_startup_task(self):
        """Create mock MCP server with blocking startup task."""
        server = Mock()
        server.name = "mock_mcp"
        server.type = "mcp_server"

        # Create a real asyncio task for testing
        async def mock_startup():
            await asyncio.sleep(0.1)
            server._startup_completed = True

        server._startup_completed = False
        server._blocking_startup_task = asyncio.create_task(mock_startup())

        return server

    @pytest.fixture
    def mock_component_with_async_start(self):
        """Create mock component with async start method."""
        component = Mock()
        component.name = "async_component"
        component.type = "component"

        async def mock_start():
            await asyncio.sleep(0.05)
            component._started = True

        component._started = False
        component.start = mock_start

        return component

    @pytest.fixture
    def mock_sync_component(self):
        """Create mock synchronous component."""
        component = Mock()
        component.name = "sync_component"
        component.type = "sync"
        # No start method or blocking startup task
        return component

    @pytest.mark.asyncio
    async def test_startup_async_components_with_mcp_servers(self, runtime, mock_mcp_server_with_startup_task):
        """Test startup_async_components waits for MCP server blocking startup tasks."""
        # Setup runtime with MCP server
        runtime.components = {"mock_mcp": mock_mcp_server_with_startup_task}

        # Verify initial state
        assert not mock_mcp_server_with_startup_task._startup_completed

        # Call startup_async_components
        await runtime.startup_async_components()

        # Verify MCP server startup task completed
        assert mock_mcp_server_with_startup_task._startup_completed

    @pytest.mark.asyncio
    async def test_startup_async_components_with_async_start_methods(self, runtime, mock_component_with_async_start):
        """Test startup_async_components calls async start methods."""
        # Setup runtime with async component
        runtime.components = {"async_comp": mock_component_with_async_start}

        # Verify initial state
        assert not mock_component_with_async_start._started

        # Call startup_async_components
        await runtime.startup_async_components()

        # Verify component was started
        assert mock_component_with_async_start._started

    @pytest.mark.asyncio
    async def test_startup_async_components_mixed_components(self, runtime, mock_mcp_server_with_startup_task,
                                                           mock_component_with_async_start, mock_sync_component):
        """Test startup_async_components with mix of async and sync components."""
        # Setup runtime with mixed components
        runtime.components = {
            "mcp": mock_mcp_server_with_startup_task,
            "async": mock_component_with_async_start,
            "sync": mock_sync_component
        }

        # Call startup_async_components
        await runtime.startup_async_components()

        # Verify async components were started
        assert mock_mcp_server_with_startup_task._startup_completed
        assert mock_component_with_async_start._started
        # Sync component should remain unchanged
        assert hasattr(mock_sync_component, 'name')

    @pytest.mark.asyncio
    async def test_startup_async_components_handles_exceptions(self, runtime):
        """Test that startup_async_components handles component startup exceptions."""
        # Create component with failing startup
        failing_component = Mock()
        failing_component.name = "failing_component"

        async def failing_start():
            await asyncio.sleep(0.05)
            raise RuntimeError("Startup failed")

        failing_component.start = failing_start

        # Create successful component
        success_component = Mock()
        success_component.name = "success_component"

        async def success_start():
            success_component._started = True

        success_component._started = False
        success_component.start = success_start

        runtime.components = {
            "failing": failing_component,
            "success": success_component
        }

        # Should not raise exception, should handle gracefully
        await runtime.startup_async_components()

        # Successful component should still have started
        assert success_component._started

    @pytest.mark.asyncio
    async def test_startup_async_components_timeout_handling(self, runtime):
        """Test that startup_async_components handles slow components with timeout."""
        # Create component that takes longer than timeout
        slow_component = Mock()
        slow_component.name = "slow_component"

        async def slow_startup():
            await asyncio.sleep(35)  # Longer than 30s timeout
            slow_component._completed = True

        slow_component._completed = False
        slow_component._blocking_startup_task = asyncio.create_task(slow_startup())

        runtime.components = {"slow": slow_component}

        import time
        start_time = time.time()

        # Should timeout and continue
        await runtime.startup_async_components()

        end_time = time.time()

        # Should not wait the full 35 seconds
        assert end_time - start_time < 35
        # Component should not have completed due to timeout
        assert not slow_component._completed

    @pytest.mark.asyncio
    async def test_startup_async_components_no_async_components(self, runtime, mock_sync_component):
        """Test startup_async_components when no async components are present."""
        # Setup runtime with only sync components
        runtime.components = {"sync": mock_sync_component}

        # Should complete quickly without issues
        await runtime.startup_async_components()

        # Sync component should be unchanged
        assert mock_sync_component.name == "sync_component"

    @pytest.mark.asyncio
    async def test_startup_async_components_empty_components(self, runtime):
        """Test startup_async_components with no components."""
        # Empty components dict
        runtime.components = {}

        # Should complete without issues
        await runtime.startup_async_components()

    @pytest.mark.asyncio
    async def test_startup_async_components_detects_coroutine_functions(self, runtime):
        """Test that startup_async_components correctly identifies coroutine functions."""
        # Component with sync start (should not be called by startup)
        sync_start_component = Mock()
        sync_start_component.name = "sync_start"
        sync_start_component._started = False

        def sync_start():
            sync_start_component._started = True

        sync_start_component.start = sync_start

        # Component with async start (should be called by startup)
        async_start_component = Mock()
        async_start_component.name = "async_start"
        async_start_component._started = False

        async def async_start():
            async_start_component._started = True

        async_start_component.start = async_start

        runtime.components = {
            "sync": sync_start_component,
            "async": async_start_component
        }

        await runtime.startup_async_components()

        # Only async component should have been started
        assert not sync_start_component._started
        assert async_start_component._started

    @pytest.mark.asyncio
    async def test_startup_async_components_logging(self, runtime, caplog):
        """Test that startup_async_components provides proper logging."""
        # Create component with async start
        component = Mock()
        component.name = "test_component"

        async def mock_start():
            component._started = True

        component.start = mock_start

        runtime.components = {"test": component}

        with caplog.at_level(logging.INFO):
            await runtime.startup_async_components()

        # Verify logging messages
        log_messages = [record.message for record in caplog.records]
        assert any("Starting async component initialization" in msg for msg in log_messages)
        assert any("Waiting for 1 async components to start" in msg for msg in log_messages)
        assert any("All async components started successfully" in msg for msg in log_messages)


class TestAsyncRuntimeIntegrationWithStartup:
    """Test AsyncRuntime integration with startup sequence."""

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration for testing."""
        return {
            "components": [],
            "test_config": True
        }

    @pytest.mark.asyncio
    async def test_runtime_start_includes_async_component_startup(self, mock_config):
        """Test that AsyncRuntime.start() includes async component startup phase."""
        runtime = AsyncRuntime()

        # Mock all the methods we don't want to actually execute
        runtime.initialize_components = AsyncMock()
        runtime.startup_async_components = AsyncMock()
        runtime._main_loop = AsyncMock()
        runtime._cleanup = AsyncMock()

        with patch.object(runtime.event_bus, 'configure_routing'):
            with patch.object(runtime, 'has_api_component', return_value=False):
                await runtime.start(mock_config)

        # Verify the startup sequence includes async component startup
        runtime.initialize_components.assert_called_once_with(mock_config)
        runtime.startup_async_components.assert_called_once()
        runtime._main_loop.assert_called_once()

    @pytest.mark.asyncio
    async def test_runtime_start_calls_startup_after_initialization(self, mock_config):
        """Test that startup_async_components is called after initialize_components."""
        runtime = AsyncRuntime()
        call_order = []

        async def mock_initialize(config):
            call_order.append("initialize")

        async def mock_startup():
            call_order.append("startup")

        async def mock_main_loop():
            call_order.append("main_loop")

        runtime.initialize_components = mock_initialize
        runtime.startup_async_components = mock_startup
        runtime._main_loop = mock_main_loop
        runtime._cleanup = AsyncMock()

        with patch.object(runtime.event_bus, 'configure_routing'):
            with patch.object(runtime, 'has_api_component', return_value=False):
                await runtime.start(mock_config)

        # Verify correct order
        assert call_order == ["initialize", "startup", "main_loop"]

    @pytest.mark.asyncio
    async def test_runtime_start_handles_startup_exceptions(self, mock_config):
        """Test that AsyncRuntime.start() handles exceptions in startup_async_components."""
        runtime = AsyncRuntime()

        runtime.initialize_components = AsyncMock()
        runtime._cleanup = AsyncMock()

        async def failing_startup():
            raise RuntimeError("Startup failed")

        runtime.startup_async_components = failing_startup

        with patch.object(runtime.event_bus, 'configure_routing'):
            # Should re-raise the exception from startup
            with pytest.raises(RuntimeError, match="Startup failed"):
                await runtime.start(mock_config)

        # Cleanup should still be called
        runtime._cleanup.assert_called_once()


class TestAsyncRuntimeComponentParsing:
    """Test AsyncRuntime component parsing with async startup requirements."""

    @pytest.fixture
    def runtime(self):
        """Create AsyncRuntime for testing."""
        return AsyncRuntime()

    @pytest.mark.asyncio
    async def test_initialize_components_registers_all_components(self, runtime):
        """Test that initialize_components registers all components properly."""
        # Mock components
        component1 = Mock()
        component1.name = "comp1"

        component2 = Mock()
        component2.name = "comp2"

        components = [component1, component2]

        # Mock the parsing to return our test components
        with patch.object(runtime, '_parse_components', return_value=components):
            with patch.object(runtime.event_bus, 'register_component') as mock_register:
                await runtime.initialize_components({"test": "config"})

        # Verify all components were registered
        assert len(runtime.components) == 2
        assert runtime.components["comp1"] == component1
        assert runtime.components["comp2"] == component2

        # Verify event bus registration
        assert mock_register.call_count == 2

    @pytest.mark.asyncio
    async def test_initialize_components_handles_parsing_errors(self, runtime):
        """Test that initialize_components handles component parsing errors."""
        # Mock parsing to raise an exception
        with patch.object(runtime, '_parse_components', side_effect=RuntimeError("Parse error")):
            await runtime.initialize_components({"test": "config"})

        # Should handle gracefully and have no components
        assert len(runtime.components) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])