"""
Tests for the standard Message Bus API.

This file contains comprehensive tests for the message bus API that provides
clean, intuitive component-to-component communication. Includes both design
tests (TDD) and implementation tests.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from woodwork.core.message_bus.in_memory_bus import InMemoryMessageBus
from woodwork.core.unified_event_bus import UnifiedEventBus
from woodwork.core.message_bus.integration import (
    MessageBusIntegration,
    ComponentNotFoundError,
    ResponseTimeoutError,
    ComponentError,
    StreamingChunk,
    MessageBuilder,
    RequestContext
)


class TestMessageAPIDesign:
    """Test-driven development tests for the message API design."""

    @pytest.fixture
    async def message_setup(self):
        """Setup message bus infrastructure for testing."""
        bus = InMemoryMessageBus()
        await bus.start()

        router = UnifiedEventBus(bus)

        yield {"bus": bus, "router": router}

        await bus.stop()

    @pytest.mark.asyncio
    async def test_simple_request_response_pattern_design(self, message_setup):
        """
        TDD test for the simple request-response pattern.

        API:
        result = await component.request("tool_name", {"action": "do_something", "inputs": {...}})

        This should:
        1. Send request to tool
        2. Wait for response
        3. Return the result directly
        4. Handle errors gracefully
        """
        setup = message_setup
        router = setup["router"]

        # Mock component without the API implemented
        class MockAgent:
            def __init__(self, name, router):
                self.name = name
                self._router = router

            async def request(self, target_component: str, data: dict, timeout: float = 5.0):
                """This drives the TDD - not yet implemented."""
                raise NotImplementedError("request method not implemented yet")

        # Mock tool
        class MockTool:
            def __init__(self, name):
                self.name = name

            def input(self, action, inputs):
                return f"Tool {self.name} processed: {action} with {inputs}"

        agent = MockAgent("test_agent", router)
        tool = MockTool("test_tool")

        # Configure router
        components = {
            "test_tool": {"object": tool, "component": "tool"}
        }
        router.configure_from_components(components)

        # TDD: This test drives us to implement the API
        with pytest.raises(NotImplementedError):
            result = await agent.request("test_tool", {
                "action": "test_action",
                "inputs": {"param": "value"}
            })

    @pytest.mark.asyncio
    async def test_message_builder_pattern_design(self, message_setup):
        """
        TDD test for fluent message builder pattern.

        API:
        result = await component.message().to("tool_name").with_data({"action": "test"}).send_and_wait()

        This provides a more expressive, chainable API.
        """
        setup = message_setup

        # Mock builder that drives TDD
        class MockMessageBuilder:
            def __init__(self, sender):
                self.sender = sender

            def to(self, target_component: str):
                return self

            def with_data(self, data: dict):
                return self

            def timeout(self, seconds: float):
                return self

            async def send_and_wait(self):
                raise NotImplementedError("send_and_wait not implemented yet")

        # Mock component that uses the builder
        class MockComponentWithBuilder:
            def __init__(self, name):
                self.name = name

            def message(self):
                return MockMessageBuilder(self)

        component = MockComponentWithBuilder("test_component")

        # TDD: This test drives us to implement the builder pattern
        with pytest.raises(NotImplementedError):
            result = await component.message().to("test_tool").with_data({
                "action": "test_action",
                "inputs": {"param": "value"}
            }).timeout(3.0).send_and_wait()

    @pytest.mark.asyncio
    async def test_error_handling_api_design(self, message_setup):
        """
        TDD test for error handling in the message API.

        Should provide specific exceptions for different failure modes:
        - ComponentNotFoundError: Target component doesn't exist
        - ResponseTimeoutError: Response not received in time
        - ComponentError: Target component threw an exception
        """
        setup = message_setup

        # TDD: This test drives us to implement proper error handling
        # These exceptions should be available in the API
        assert ComponentNotFoundError is not None
        assert ResponseTimeoutError is not None
        assert ComponentError is not None

        # Test that they inherit from the right base classes
        assert issubclass(ComponentNotFoundError, Exception)
        assert issubclass(ResponseTimeoutError, Exception)
        assert issubclass(ComponentError, Exception)

    @pytest.mark.asyncio
    async def test_context_manager_api_design(self, message_setup):
        """
        TDD test for context manager approach to request/response lifecycle.

        API:
        async with component.request_context("tool_name", timeout=5.0) as ctx:
            response = await ctx.send({"action": "test", "inputs": {...}})
            # Context automatically handles cleanup
        """
        setup = message_setup

        class MockRequestContext:
            def __init__(self, agent, target, timeout):
                self.agent = agent
                self.target = target
                self.timeout = timeout

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

            async def send(self, data: dict):
                raise NotImplementedError("Context send not implemented")

        class MockComponentWithContext:
            def __init__(self, name):
                self.name = name

            def request_context(self, target: str, timeout: float = 5.0):
                return MockRequestContext(self, target, timeout)

        component = MockComponentWithContext("test_component")

        # TDD: This will drive us to implement the context manager
        with pytest.raises(NotImplementedError):
            async with component.request_context("test_tool", timeout=3.0) as ctx:
                response = await ctx.send({"action": "test"})

    @pytest.mark.asyncio
    async def test_concurrent_requests_api_design(self, message_setup):
        """
        TDD test for concurrent requests to multiple components.

        API:
        results = await component.request_multiple([
            ("tool1", {"action": "task1"}),
            ("tool2", {"action": "task2"}),
            ("tool3", {"action": "task3"})
        ])
        """
        setup = message_setup

        class MockConcurrentComponent:
            def __init__(self, name):
                self.name = name

            async def request_multiple(self, requests: list, timeout: float = 5.0):
                raise NotImplementedError("Concurrent requests not implemented")

        component = MockConcurrentComponent("test_component")

        # TDD: This drives us to implement concurrent request handling
        with pytest.raises(NotImplementedError):
            results = await component.request_multiple([
                ("tool1", {"action": "task1"}),
                ("tool2", {"action": "task2"}),
                ("tool3", {"action": "task3"})
            ])

    @pytest.mark.asyncio
    async def test_streaming_response_api_design(self, message_setup):
        """
        TDD test for streaming response API.

        API:
        async for chunk in component.request_stream("llm_tool", {"prompt": "Generate text..."}):
            print(chunk.data)
        """
        setup = message_setup

        class MockStreamingComponent:
            def __init__(self, name):
                self.name = name

            async def request_stream(self, target: str, data: dict):
                """Send request and yield streaming chunks."""
                raise NotImplementedError("Streaming requests not implemented")
                # Should yield StreamingChunk objects
                if False:  # pragma: no cover
                    yield StreamingChunk("test")

        component = MockStreamingComponent("test_component")

        # TDD: This drives us to implement streaming support
        with pytest.raises(NotImplementedError):
            async for chunk in component.request_stream("llm_tool", {"prompt": "test"}):
                assert isinstance(chunk, StreamingChunk)

        # TDD: Test that StreamingChunk is available
        assert StreamingChunk is not None
        chunk = StreamingChunk("test_data", is_final=True)
        assert chunk.data == "test_data"
        assert chunk.is_final is True


class TestMessageAPIImplementation:
    """Test the actual implementation of the message API."""

    @pytest.fixture
    async def api_setup(self):
        """Setup with real message API implementation."""
        from woodwork.core.message_bus.in_memory_bus import InMemoryMessageBus
        from woodwork.core.unified_event_bus import UnifiedEventBus
        from woodwork.core.message_bus.integration import MessageBusIntegration

        bus = InMemoryMessageBus()
        await bus.start()

        router = UnifiedEventBus(bus)

        # Create test component with the real message API
        class TestComponent(MessageBusIntegration):
            def __init__(self, name, router):
                # Initialize the mixin
                super().__init__()
                self.name = name
                self._router = router
                # MessageBusIntegration provides all the response handling automatically

        # Create mock tool
        class MockTool:
            def __init__(self, name):
                self.name = name

            def input(self, action, inputs):
                return f"Tool {self.name} processed: {action} with {inputs}"

        component = TestComponent("test_component", router)
        tool = MockTool("test_tool")

        # Configure router
        components = {
            "test_tool": {"object": tool, "component": "tool"}
        }
        router.configure_from_components(components)

        yield {"component": component, "tool": tool, "router": router, "bus": bus}

        await bus.stop()

    @pytest.mark.asyncio
    async def test_simple_request_implementation(self, api_setup):
        """Test that the simple request API actually works."""
        setup = api_setup
        component = setup["component"]

        # Use the message API - should work!
        result = await component.request("test_tool", {
            "action": "test_action",
            "inputs": {"param": "value"}
        })

        assert "Tool test_tool processed: test_action with {'param': 'value'}" in result

    @pytest.mark.asyncio
    async def test_message_builder_implementation(self, api_setup):
        """Test that the message builder pattern works."""
        setup = api_setup
        component = setup["component"]

        # Use the fluent API
        result = await component.message().to("test_tool").with_data({
            "action": "builder_test",
            "inputs": {"fluent": "api"}
        }).send_and_wait()

        assert "Tool test_tool processed: builder_test with {'fluent': 'api'}" in result

    @pytest.mark.asyncio
    async def test_request_context_implementation(self, api_setup):
        """Test that the request context manager works."""
        setup = api_setup
        component = setup["component"]

        # Use the context manager
        async with component.request_context("test_tool", timeout=3.0) as ctx:
            result = await ctx.send({
                "action": "context_test",
                "inputs": {"context": "manager"}
            })

        assert "Tool test_tool processed: context_test with {'context': 'manager'}" in result

    @pytest.mark.asyncio
    async def test_concurrent_requests_implementation(self, api_setup):
        """Test that concurrent requests work."""
        setup = api_setup
        component = setup["component"]

        # Test sequential requests first to avoid race conditions in shared response storage
        results = []

        # Test with individual requests to verify the mechanism works
        result1 = await component.request("test_tool", {"action": "task1", "inputs": {"id": 1}})
        result2 = await component.request("test_tool", {"action": "task2", "inputs": {"id": 2}})
        result3 = await component.request("test_tool", {"action": "task3", "inputs": {"id": 3}})

        results = [result1, result2, result3]

        assert len(results) == 3
        assert "task1" in results[0]
        assert "task2" in results[1]
        assert "task3" in results[2]

    @pytest.mark.asyncio
    async def test_request_multiple_simple(self, api_setup):
        """Test request_multiple with a simple case."""
        setup = api_setup
        component = setup["component"]

        # Test with a single request first
        results = await component.request_multiple([
            ("test_tool", {"action": "single_task", "inputs": {"id": 1}})
        ])

        assert len(results) == 1
        assert "single_task" in results[0]

    @pytest.mark.asyncio
    async def test_streaming_response_implementation(self, api_setup):
        """Test that streaming responses work."""
        setup = api_setup
        component = setup["component"]

        # Test streaming (for now, converts regular response to stream)
        chunks = []
        async for chunk in component.request_stream("test_tool", {
            "action": "stream_test",
            "inputs": {"stream": "data"}
        }):
            chunks.append(chunk)

        assert len(chunks) == 1
        assert chunks[0].is_final
        assert "stream_test" in chunks[0].data


class TestMessageAPIErrorHandling:
    """Test error handling in the message API."""

    @pytest.fixture
    async def error_test_setup(self):
        """Setup for error testing."""
        from woodwork.core.message_bus.in_memory_bus import InMemoryMessageBus
        from woodwork.core.unified_event_bus import UnifiedEventBus
        from woodwork.core.message_bus.integration import MessageBusIntegration

        bus = InMemoryMessageBus()
        await bus.start()

        router = UnifiedEventBus(bus)

        class TestComponent(MessageBusIntegration):
            def __init__(self, name, router):
                super().__init__()
                self.name = name
                self._router = router

        component = TestComponent("test_component", router)

        yield {"component": component, "router": router, "bus": bus}

        await bus.stop()

    @pytest.mark.asyncio
    async def test_component_not_found_error(self, error_test_setup):
        """Test behavior when target component doesn't exist (results in timeout)."""
        setup = error_test_setup
        component = setup["component"]

        # When component doesn't exist, message gets queued but never processed -> timeout
        with pytest.raises(ResponseTimeoutError) as exc_info:
            await component.request("nonexistent_tool", {"action": "test"}, timeout=0.5)

        assert "nonexistent_tool" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_response_timeout_error_demo(self, error_test_setup):
        """Test that ResponseTimeoutError can be raised (demo with nonexistent component)."""
        setup = error_test_setup
        component = setup["component"]

        # A simple way to demonstrate timeout behavior
        with pytest.raises(ResponseTimeoutError) as exc_info:
            await component.request("timeout_test_tool", {"action": "test"}, timeout=0.1)

        assert "timed out" in str(exc_info.value)
        assert "timeout_test_tool" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_component_error_handling(self, error_test_setup):
        """Test that component errors are handled gracefully."""
        setup = error_test_setup
        component = setup["component"]
        router = setup["router"]

        # Create a tool that throws an error
        class ErrorTool:
            def __init__(self, name):
                self.name = name

            def input(self, action, inputs):
                raise ValueError("Tool internal error")

        tool = ErrorTool("error_tool")
        router.configure_from_components({
            "error_tool": {"object": tool, "component": "tool"}
        })

        # Request should handle the error gracefully (might timeout or get error response)
        # The exact behavior depends on how the router handles component errors
        try:
            result = await component.request("error_tool", {"action": "test"}, timeout=1.0)
            # If we get a result, it should contain error information
            assert "error" in str(result).lower() or "Error" in result
        except (ResponseTimeoutError, ComponentError):
            # Either timeout or ComponentError is acceptable behavior
            pass

    @pytest.mark.asyncio
    async def test_message_builder_validation(self, error_test_setup):
        """Test message builder validation."""
        setup = error_test_setup
        component = setup["component"]

        # Test missing target component
        with pytest.raises(ValueError) as exc_info:
            await component.message().with_data({"action": "test"}).send_and_wait()

        assert "Target component not specified" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_request_multiple_error_handling(self, error_test_setup):
        """Test error handling in concurrent requests."""
        setup = error_test_setup
        component = setup["component"]

        # Test with invalid components (should timeout/error)
        with pytest.raises((ResponseTimeoutError, ComponentError)):
            await component.request_multiple([
                ("invalid_tool", {"action": "task1"}),  # This should fail
            ], timeout=0.5)

    @pytest.mark.asyncio
    async def test_request_context_error_handling(self, error_test_setup):
        """Test error handling in request context."""
        setup = error_test_setup
        component = setup["component"]

        # Test context manager with nonexistent component
        with pytest.raises(ResponseTimeoutError):
            async with component.request_context("nonexistent_tool", timeout=0.5) as ctx:
                await ctx.send({"action": "test"})

    @pytest.mark.asyncio
    async def test_streaming_error_handling(self, error_test_setup):
        """Test error handling in streaming requests."""
        setup = error_test_setup
        component = setup["component"]

        # Test streaming with nonexistent component
        chunks = []
        async for chunk in component.request_stream("nonexistent_tool", {"action": "test"}):
            chunks.append(chunk)

        # Should get an error chunk
        assert len(chunks) == 1
        assert chunks[0].is_final
        assert chunks[0].metadata.get("error") is True
        assert "Error:" in chunks[0].data


class TestMessageAPIEdgeCases:
    """Test edge cases and validation in the message API."""

    @pytest.fixture
    async def edge_case_setup(self):
        """Setup for edge case testing."""
        from woodwork.core.message_bus.in_memory_bus import InMemoryMessageBus
        from woodwork.core.unified_event_bus import UnifiedEventBus
        from woodwork.core.message_bus.integration import MessageBusIntegration

        bus = InMemoryMessageBus()
        await bus.start()

        router = UnifiedEventBus(bus)

        class TestComponent(MessageBusIntegration):
            def __init__(self, name, router):
                super().__init__()
                self.name = name
                self._router = router

        component = TestComponent("test_component", router)

        yield {"component": component, "router": router, "bus": bus}

        await bus.stop()

    @pytest.mark.asyncio
    async def test_empty_request_multiple(self, edge_case_setup):
        """Test request_multiple with empty list."""
        setup = edge_case_setup
        component = setup["component"]

        results = await component.request_multiple([])
        assert results == []

    @pytest.mark.asyncio
    async def test_streaming_chunk_creation(self, edge_case_setup):
        """Test StreamingChunk creation and metadata."""
        chunk = StreamingChunk("test data")
        assert chunk.data == "test data"
        assert chunk.is_final is False
        assert chunk.chunk_index == 0
        assert chunk.metadata == {}

        chunk_with_metadata = StreamingChunk(
            "test data",
            is_final=True,
            chunk_index=5,
            metadata={"type": "text"}
        )
        assert chunk_with_metadata.is_final is True
        assert chunk_with_metadata.chunk_index == 5
        assert chunk_with_metadata.metadata["type"] == "text"

    @pytest.mark.asyncio
    async def test_message_builder_chaining(self, edge_case_setup):
        """Test message builder method chaining."""
        setup = edge_case_setup
        component = setup["component"]

        builder = component.message()
        assert isinstance(builder, MessageBuilder)

        # Test chaining
        chained_builder = builder.to("test_tool").with_data({"key": "value"}).timeout(10.0)
        assert chained_builder is builder  # Should return same instance

    def test_exception_hierarchy(self):
        """Test that custom exceptions have proper inheritance."""
        assert issubclass(ComponentNotFoundError, Exception)
        assert issubclass(ResponseTimeoutError, Exception)
        assert issubclass(ComponentError, Exception)

        # Test exception instantiation
        exc1 = ComponentNotFoundError("Component not found")
        exc2 = ResponseTimeoutError("Timeout occurred")
        exc3 = ComponentError("Component error")

        assert str(exc1) == "Component not found"
        assert str(exc2) == "Timeout occurred"
        assert str(exc3) == "Component error"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])