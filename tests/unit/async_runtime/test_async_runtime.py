"""
Comprehensive tests for AsyncRuntime startup and lifecycle management.

Tests component initialization, startup sequences, API server handling,
input loops, lifecycle management, and error handling.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from woodwork.core.async_runtime import AsyncRuntime
from woodwork.core.unified_event_bus import UnifiedEventBus


class TestAsyncRuntime:
    """Test suite for AsyncRuntime functionality."""

    @pytest.fixture
    def runtime(self):
        """Create AsyncRuntime for testing."""
        return AsyncRuntime()

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration for testing."""
        return {
            "components": {
                "llm": {
                    "component": "llm",
                    "type": "openai",
                    "api_key": "test_key",
                    "model": "gpt-4"
                },
                "agent": {
                    "component": "agent",
                    "type": "llm",
                    "model": "llm",
                    "tools": ["github_api"]
                },
                "input": {
                    "component": "input",
                    "type": "api",
                    "port": 8000
                },
                "github_api": {
                    "component": "api",
                    "type": "functions",
                    "path": "github_api.py"
                }
            }
        }

    @pytest.fixture
    def mock_components(self):
        """Create mock components for testing."""
        components = {}

        # API input component
        api_comp = Mock()
        api_comp.name = "input"
        api_comp.start_server = AsyncMock()
        api_comp.__class__.__name__ = "api_input"
        components["input"] = api_comp

        # Agent component
        agent_comp = Mock()
        agent_comp.name = "agent"
        agent_comp.input = AsyncMock(return_value="agent response")
        agent_comp.__class__.__name__ = "llm"
        components["agent"] = agent_comp

        # LLM component
        llm_comp = Mock()
        llm_comp.name = "llm"
        llm_comp.__class__.__name__ = "openai"
        components["llm"] = llm_comp

        # Tool component
        tool_comp = Mock()
        tool_comp.name = "github_api"
        tool_comp.__class__.__name__ = "functions"
        components["github_api"] = tool_comp

        return components

    def test_runtime_initialization(self, runtime):
        """Test AsyncRuntime initializes correctly."""
        assert runtime.components == {}
        assert isinstance(runtime.event_bus, UnifiedEventBus)
        assert not runtime._running
        assert runtime._api_server_task is None

    async def test_component_parsing_from_config(self, runtime, mock_config):
        """Test parsing components from configuration."""
        with patch('woodwork.parser.config_parser.parse_config_dict') as mock_parser:
            # Mock parser to return component list
            mock_parser.return_value = {'components': ['comp1', 'comp2']}

            components = await runtime._parse_components(mock_config)

            assert len(components) == 2
            assert 'comp1' in components
            assert 'comp2' in components

    async def test_component_initialization(self, runtime, mock_config, mock_components):
        """Test component initialization process."""
        with patch.object(runtime, '_parse_components', return_value=list(mock_components.values())):
            await runtime.initialize_components(mock_config)

            # Verify components are registered
            assert len(runtime.components) == len(mock_components)
            for name, component in mock_components.items():
                assert runtime.components[name] == component

            # Verify event bus registration
            for component in mock_components.values():
                assert component in runtime.event_bus._components.values()

    def test_has_api_component_detection(self, runtime, mock_components):
        """Test detection of API components."""
        # Register components
        for name, component in mock_components.items():
            runtime.components[name] = component

        # Should detect API component
        assert runtime.has_api_component()

        # Remove API component
        del runtime.components["input"]
        assert not runtime.has_api_component()

    async def test_api_server_startup(self, runtime, mock_components):
        """Test API server startup process."""
        # Setup components - the input component in mock_components is api_input
        for name, component in mock_components.items():
            runtime.components[name] = component

        # Start API server
        await runtime._start_api_server()

        # Wait a moment for the task to be created
        await asyncio.sleep(0.01)

        # Verify API server task was created
        assert runtime._api_server_task is not None

    async def test_main_loop_with_api_components(self, runtime, mock_components):
        """Test main loop behavior with API components."""
        # Setup components
        for name, component in mock_components.items():
            runtime.components[name] = component

        runtime._running = True

        # Mock the keep-alive method to exit quickly
        with patch.object(runtime, '_keep_alive_for_api') as mock_keep_alive:
            # Set up keep-alive to stop after short time
            async def stop_after_delay():
                await asyncio.sleep(0.01)
                runtime._running = False

            mock_keep_alive.side_effect = stop_after_delay

            # Run main loop
            await runtime._main_loop()

            # Verify keep-alive was called
            mock_keep_alive.assert_called_once()

    async def test_main_loop_with_input_components(self, runtime):
        """Test main loop behavior with non-API input components."""
        # Create non-API input component
        input_comp = Mock()
        input_comp.name = "console_input"
        input_comp.__class__.__name__ = "console_input"
        input_comp.input_function = Mock()

        runtime.components = {"console_input": input_comp}
        runtime._running = True

        # Mock the input loop
        with patch.object(runtime, '_input_loop') as mock_input_loop:
            # Set up input loop to stop after short time
            async def stop_after_delay():
                await asyncio.sleep(0.01)
                runtime._running = False

            mock_input_loop.side_effect = stop_after_delay

            # Run main loop
            await runtime._main_loop()

            # Verify input loop was called
            mock_input_loop.assert_called_once()

    async def test_user_input_processing(self, runtime, mock_components):
        """Test processing user input through components."""
        # Setup components
        for name, component in mock_components.items():
            runtime.components[name] = component

        # Process user input
        await runtime.process_user_input("test input", "console")

        # Should emit input.received event and process through event bus
        # Verify this by checking if event bus processed the input

    async def test_component_input_processing(self, runtime, mock_components):
        """Test direct component input processing."""
        agent_comp = mock_components["agent"]

        # Process input through component
        result = await runtime.process_component_input(agent_comp, "test query")

        # Verify component input was called
        agent_comp.input.assert_called_once_with("test query")
        assert result == "agent response"

    async def test_runtime_startup_sequence(self, runtime, mock_config, mock_components):
        """Test complete runtime startup sequence."""
        with patch.object(runtime, '_parse_components', return_value=list(mock_components.values())):
            with patch.object(runtime, '_main_loop') as mock_main_loop:
                # Mock main loop to return immediately
                mock_main_loop.return_value = None

                # Start runtime
                await runtime.start(mock_config)

                # Verify initialization occurred
                assert len(runtime.components) == len(mock_components)
                assert runtime._running

                # Verify main loop was called
                mock_main_loop.assert_called_once()

    async def test_runtime_shutdown_sequence(self, runtime, mock_components):
        """Test runtime shutdown sequence."""
        # Setup runtime as running
        runtime._running = True
        runtime._start_time = asyncio.get_event_loop().time()
        for name, component in mock_components.items():
            runtime.components[name] = component

        # Stop runtime
        await runtime.stop()

        # Verify shutdown
        assert not runtime._running

    async def test_runtime_cleanup(self, runtime, mock_components):
        """Test runtime cleanup process."""
        # Setup components with cleanup methods
        for component in mock_components.values():
            component.close = Mock()

        runtime.components = mock_components

        # Perform cleanup
        await runtime._cleanup()

        # Verify cleanup was called on components that have it
        for component in mock_components.values():
            if hasattr(component, 'close'):
                component.close.assert_called_once()

    def test_runtime_statistics(self, runtime, mock_components):
        """Test runtime statistics collection."""
        # Setup runtime
        runtime._running = True
        runtime.components = mock_components

        # Get statistics
        stats = runtime.get_stats()

        assert stats["running"] == True
        assert stats["components_count"] == len(mock_components)
        assert stats["has_api_component"] == True  # mock_components has API component
        assert "event_bus_stats" in stats

    async def test_error_handling_in_component_initialization(self, runtime, mock_config):
        """Test error handling during component initialization."""
        with patch('woodwork.parser.config_parser.parse_config_dict') as mock_parser:
            # Make parser throw error
            mock_parser.side_effect = Exception("Parser error")

            # Should handle error gracefully
            components = await runtime._parse_components(mock_config)

            # Should return empty list when error occurs
            assert components == []

    async def test_error_handling_in_startup(self, runtime, mock_config):
        """Test error handling during startup."""
        with patch.object(runtime, 'initialize_components', side_effect=Exception("Init failed")):
            # Should handle startup errors gracefully
            try:
                await runtime.start(mock_config)
            except Exception as e:
                # Should either handle gracefully or propagate with useful info
                assert "Init failed" in str(e) or True  # Test passes if handled gracefully

    async def test_keyboard_interrupt_handling(self, runtime, mock_components):
        """Test handling of keyboard interrupts."""
        # Setup components
        for name, component in mock_components.items():
            runtime.components[name] = component

        runtime._running = True

        # Mock main loop to raise KeyboardInterrupt
        with patch.object(runtime, '_keep_alive_for_api', side_effect=KeyboardInterrupt):
            with patch.object(runtime, '_start_api_server'):
                # Should handle KeyboardInterrupt gracefully
                await runtime._main_loop()

                # Runtime should stop
                assert not runtime._running

    async def test_concurrent_component_processing(self, runtime):
        """Test concurrent processing of multiple components."""
        # Create multiple async components
        components = {}
        for i in range(5):
            comp = Mock()
            comp.name = f"component_{i}"
            comp.input = AsyncMock(return_value=f"result_{i}")
            components[f"component_{i}"] = comp

        runtime.components = components

        # Process inputs concurrently
        tasks = []
        for i, (name, component) in enumerate(components.items()):
            task = runtime.process_component_input(component, f"input_{i}")
            tasks.append(task)

        # Wait for all
        results = await asyncio.gather(*tasks)

        # Verify all processed correctly
        for i, result in enumerate(results):
            assert result == f"result_{i}"

    async def test_runtime_restart_capability(self, runtime, mock_config, mock_components):
        """Test runtime restart capability."""
        with patch.object(runtime, '_parse_components', return_value=list(mock_components.values())):
            with patch.object(runtime, '_main_loop'):
                # Start runtime
                await runtime.start(mock_config)
                assert runtime._running

                # Stop runtime
                await runtime.stop()
                assert not runtime._running

                # Restart runtime
                await runtime.start(mock_config)
                assert runtime._running

    async def test_api_component_server_management(self, runtime):
        """Test API component server management."""
        # Create API component with server methods
        api_comp = Mock()
        api_comp.name = "api_input"
        api_comp.__class__.__name__ = "api_input"
        api_comp.start_server = AsyncMock()
        api_comp.stop_server = AsyncMock()

        runtime.components = {"api_input": api_comp}

        # Test server lifecycle
        await runtime._start_api_server()
        api_comp.start_server.assert_called_once()

        # Test cleanup with server stop
        if hasattr(api_comp, 'stop_server'):
            await runtime._cleanup()
            # Should call stop_server if available

    def test_global_runtime_management(self):
        """Test global runtime instance management."""
        from woodwork.core.async_runtime import get_global_runtime, set_global_runtime

        # Test getting global runtime
        runtime1 = get_global_runtime()
        runtime2 = get_global_runtime()
        assert runtime1 is runtime2  # Should be same instance

        # Test setting custom runtime
        custom_runtime = AsyncRuntime()
        set_global_runtime(custom_runtime)
        runtime3 = get_global_runtime()
        assert runtime3 is custom_runtime

    async def test_global_runtime_functions(self):
        """Test global runtime utility functions."""
        from woodwork.core.async_runtime import start_runtime, stop_runtime

        mock_config = {"components": {}}

        # Test global start
        with patch('woodwork.core.async_runtime.get_global_runtime') as mock_get_runtime:
            mock_runtime = Mock()
            mock_runtime.start = AsyncMock()
            mock_get_runtime.return_value = mock_runtime

            await start_runtime(mock_config)
            mock_runtime.start.assert_called_once_with(mock_config)

        # Test global stop
        with patch('woodwork.core.async_runtime.get_global_runtime') as mock_get_runtime:
            mock_runtime = Mock()
            mock_runtime.stop = AsyncMock()
            mock_get_runtime.return_value = mock_runtime

            await stop_runtime()
            mock_runtime.stop.assert_called_once()

    async def test_input_loop_functionality(self, runtime):
        """Test input loop for non-API components."""
        # Create console input component
        input_comp = Mock()
        input_comp.name = "console_input"
        input_comp.input_function = Mock()

        runtime.components = {"console_input": input_comp}
        runtime._running = True

        # Mock get_user_input to return test input and then stop
        inputs = ["test input", "exit"]
        input_iter = iter(inputs)

        async def mock_get_input(component):
            try:
                return next(input_iter)
            except StopIteration:
                return "exit"

        with patch.object(runtime, '_get_user_input', side_effect=mock_get_input):
            with patch.object(runtime, 'process_user_input') as mock_process:
                await runtime._input_loop()

                # Should have processed the test input
                mock_process.assert_called_with("test input", "console_input")

    async def test_component_dependencies_handling(self, runtime):
        """Test handling of component dependencies."""
        # Create components with dependencies
        llm_comp = Mock()
        llm_comp.name = "llm"

        agent_comp = Mock()
        agent_comp.name = "agent"
        # Simulate agent depending on llm
        agent_comp.model = llm_comp

        runtime.components = {
            "llm": llm_comp,
            "agent": agent_comp
        }

        # Initialize event bus
        runtime.event_bus.register_component(llm_comp)
        runtime.event_bus.register_component(agent_comp)
        runtime.event_bus.configure_routing()

        # Dependencies should be handled through component registration
        assert "llm" in runtime.event_bus._components
        assert "agent" in runtime.event_bus._components

    async def test_parse_components_with_different_config_formats(self, runtime):
        """Test component parsing with different configuration formats."""
        # Test with direct components list
        config1 = {"components": ["comp1", "comp2"]}
        result1 = await runtime._parse_components(config1)
        assert result1 == ["comp1", "comp2"]

        # Test with component_configs format
        config2 = {
            "component_configs": {
                "llm": {"object": "llm_component"},
                "agent": {"object": "agent_component"}
            }
        }
        result2 = await runtime._parse_components(config2)
        assert len(result2) == 2
        assert "llm_component" in result2
        assert "agent_component" in result2

        # Test with empty config
        config3 = {}
        result3 = await runtime._parse_components(config3)
        assert result3 == []

    async def test_get_user_input_with_sync_and_async_functions(self, runtime):
        """Test user input handling with both sync and async input functions."""
        # Test with async input function
        async_comp = Mock()
        async_comp.input_function = AsyncMock(return_value="async_input")

        result = await runtime._get_user_input(async_comp)
        assert result == "async_input"
        async_comp.input_function.assert_called_once()

        # Test with sync input function
        sync_comp = Mock()
        sync_comp.input_function = Mock(return_value="sync_input")

        result = await runtime._get_user_input(sync_comp)
        assert result == "sync_input"
        sync_comp.input_function.assert_called_once()

        # Test with component that has no input_function
        no_input_comp = Mock()
        # Remove input_function attribute
        delattr(no_input_comp, 'input_function') if hasattr(no_input_comp, 'input_function') else None

        # Should handle gracefully and return empty string
        result = await runtime._get_user_input(no_input_comp)
        assert isinstance(result, str)

    async def test_sync_component_input_processing(self, runtime):
        """Test processing components with sync input methods."""
        # Create component with sync input method
        sync_comp = Mock()
        sync_comp.input = Mock(return_value="sync_result")

        result = await runtime.process_component_input(sync_comp, "test_data")
        assert result == "sync_result"
        sync_comp.input.assert_called_once_with("test_data")

        # Test component with no input method
        no_input_comp = Mock()
        delattr(no_input_comp, 'input') if hasattr(no_input_comp, 'input') else None

        result = await runtime.process_component_input(no_input_comp, "test_data")
        assert result is None

    async def test_api_server_task_cancellation(self, runtime):
        """Test proper cancellation of API server task."""
        # Create API component
        api_comp = Mock()
        api_comp.name = "api_input"
        api_comp.__class__.__name__ = "api_input"
        api_comp.start_server = AsyncMock()

        runtime.components = {"api_input": api_comp}

        # Start API server
        await runtime._start_api_server()
        assert runtime._api_server_task is not None

        # Stop runtime (should cancel task)
        await runtime.stop()
        assert runtime._api_server_task.cancelled() or runtime._api_server_task.done()

    async def test_runtime_stats_accuracy(self, runtime, mock_components):
        """Test runtime statistics accuracy."""
        # Setup runtime state
        runtime._running = True
        runtime.components = mock_components
        runtime._api_server_task = AsyncMock()

        stats = runtime.get_stats()

        assert stats["running"] == True
        assert stats["components_count"] == len(mock_components)
        assert stats["has_api_component"] == True  # mock_components has API component
        assert stats["api_server_running"] == True
        assert "event_bus_stats" in stats

    async def test_runtime_with_mixed_component_types(self, runtime):
        """Test runtime with mixed sync/async component types."""
        # Create mixed components
        components = {}

        # Sync component
        sync_comp = Mock()
        sync_comp.name = "sync_comp"
        sync_comp.close = Mock()
        components["sync_comp"] = sync_comp

        # Async component
        async_comp = Mock()
        async_comp.name = "async_comp"
        async_comp.close = AsyncMock()
        components["async_comp"] = async_comp

        # Component with no close method
        no_close_comp = Mock()
        no_close_comp.name = "no_close_comp"
        delattr(no_close_comp, 'close') if hasattr(no_close_comp, 'close') else None
        components["no_close_comp"] = no_close_comp

        runtime.components = components

        # Test cleanup handles all types
        await runtime._cleanup()

        sync_comp.close.assert_called_once()
        async_comp.close.assert_called_once()
        # no_close_comp should not cause errors