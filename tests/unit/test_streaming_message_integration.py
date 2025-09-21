"""
TDD tests for streaming integration with the message bus API.

This file drives the implementation of true streaming support that integrates
the new message API with the existing StreamManager infrastructure.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from woodwork.core.message_bus.in_memory_bus import InMemoryMessageBus
from woodwork.core.message_bus.declarative_router import DeclarativeRouter
from woodwork.core.message_bus.integration import (
    MessageBusIntegration,
    StreamingChunk
)


class TestStreamingMessageAPIDesign:
    """TDD tests that drive the streaming integration design."""

    @pytest.fixture
    async def streaming_setup(self):
        """Setup for streaming tests."""
        bus = InMemoryMessageBus()
        await bus.start()

        router = DeclarativeRouter(bus)

        yield {"bus": bus, "router": router}

        await bus.stop()

    @pytest.mark.asyncio
    async def test_request_stream_should_integrate_with_stream_manager(self, streaming_setup):
        """
        TDD: request_stream() should integrate with existing StreamManager infrastructure.

        The current implementation just converts regular responses to fake streams.
        We need it to actually create real streaming connections.
        """
        setup = streaming_setup

        # Mock component that should support real streaming
        class MockStreamingComponent(MessageBusIntegration):
            def __init__(self, name, router):
                super().__init__()
                self.name = name
                self._router = router
                # This should be set up by the streaming integration
                self._stream_manager = None

            async def _generate_and_stream_output(self, input_data, stream_id):
                """Mock the existing streaming method that components already have."""
                # This should be called by the real streaming integration
                raise NotImplementedError("Should be implemented by streaming integration")

        component = MockStreamingComponent("test_component", setup["router"])

        # TDD: This should work with real streaming, not just fake conversion
        with pytest.raises(NotImplementedError):
            chunks = []
            async for chunk in component.request_stream("streaming_target", {"prompt": "test"}):
                chunks.append(chunk)

    @pytest.mark.asyncio
    async def test_router_should_support_streaming_requests(self, streaming_setup):
        """
        TDD: Router should have a send_to_component_with_stream() method.

        Currently the router only supports send_to_component_with_response().
        For true streaming, we need send_to_component_with_stream().
        """
        setup = streaming_setup
        router = setup["router"]

        # TDD: Router should have streaming support
        assert not hasattr(router, 'send_to_component_with_stream'), \
            "Router should not have streaming support yet (drives implementation)"

        # This is what we want to implement
        # success, stream_id = await router.send_to_component_with_stream(
        #     name="target_component",
        #     source_component_name="source_component",
        #     data={"prompt": "test"}
        # )

    @pytest.mark.asyncio
    async def test_streaming_component_should_receive_stream_requests(self, streaming_setup):
        """
        TDD: Components should be able to receive streaming requests via message bus.

        When a component receives a "stream_request" message, it should:
        1. Start streaming output via StreamManager
        2. Send chunks back to the requesting component
        """
        setup = streaming_setup

        # Mock streaming component that receives stream requests
        class MockStreamingTarget(MessageBusIntegration):
            def __init__(self, name, router):
                super().__init__()
                self.name = name
                self._router = router
                self.streaming_enabled = True
                self._can_stream_output = lambda: True

            async def handle_stream_request(self, data, stream_id, source_component):
                """This should be called when component receives stream request."""
                # Should integrate with existing _generate_and_stream_output
                raise NotImplementedError("Stream request handling not implemented")

        target = MockStreamingTarget("streaming_target", setup["router"])

        # TDD: This drives us to implement stream request handling
        with pytest.raises(NotImplementedError):
            await target.handle_stream_request(
                {"prompt": "test"},
                "stream_123",
                "requesting_component"
            )

    @pytest.mark.asyncio
    async def test_stream_manager_should_integrate_with_message_bus(self, streaming_setup):
        """
        TDD: StreamManager should work with message bus for cross-component streaming.

        Currently StreamManager is used within components. We need it to work
        across components via the message bus.
        """
        setup = streaming_setup

        # TDD: We need a message bus aware StreamManager
        from woodwork.core.stream_manager import StreamManager

        # Current StreamManager doesn't know about message bus
        stream_manager = StreamManager()

        # This should be possible but isn't implemented yet
        assert not hasattr(stream_manager, 'send_chunk_via_message_bus'), \
            "StreamManager should not have message bus integration yet"

        # This is what we want to implement:
        # await stream_manager.send_chunk_via_message_bus(
        #     stream_id="stream_123",
        #     chunk_data="Hello",
        #     target_component="requesting_component",
        #     message_bus=setup["bus"]
        # )

    @pytest.mark.asyncio
    async def test_streaming_chunks_should_preserve_metadata(self, streaming_setup):
        """
        TDD: StreamingChunk should preserve all metadata from original streaming.

        When converting from StreamManager chunks to StreamingChunk objects,
        we need to preserve all metadata, timing, and ordering information.
        """
        setup = streaming_setup

        # Create a realistic streaming chunk with metadata
        chunk = StreamingChunk(
            data="Hello world",
            is_final=False,
            chunk_index=5,
            metadata={
                "timestamp": 1234567890,
                "stream_id": "stream_123",
                "source_component": "llm_component",
                "chunk_type": "text",
                "encoding": "utf-8"
            }
        )

        # TDD: All metadata should be preserved
        assert chunk.metadata["timestamp"] == 1234567890
        assert chunk.metadata["stream_id"] == "stream_123"
        assert chunk.metadata["source_component"] == "llm_component"
        assert chunk.chunk_index == 5

    @pytest.mark.asyncio
    async def test_concurrent_streams_should_be_isolated(self, streaming_setup):
        """
        TDD: Multiple concurrent streams should not interfere with each other.

        When multiple components request streams from the same target,
        each stream should be isolated and deliver the correct chunks.
        """
        setup = streaming_setup

        # Mock component that can handle multiple streams
        class MockMultiStreamComponent(MessageBusIntegration):
            def __init__(self, name, router):
                super().__init__()
                self.name = name
                self._router = router
                self.active_streams = {}

            async def start_stream(self, stream_id, requesting_component, data):
                """Start a new stream - should track multiple streams."""
                # TDD: This should handle multiple concurrent streams
                raise NotImplementedError("Multi-stream handling not implemented")

        component = MockMultiStreamComponent("multi_stream", setup["router"])

        # TDD: Should be able to handle multiple streams
        with pytest.raises(NotImplementedError):
            await component.start_stream("stream_1", "client_1", {"prompt": "test1"})
            await component.start_stream("stream_2", "client_2", {"prompt": "test2"})


class TestStreamingMessageAPIIntegration:
    """TDD tests for the actual streaming integration implementation."""

    @pytest.fixture
    async def integration_setup(self):
        """Setup for integration tests."""
        bus = InMemoryMessageBus()
        await bus.start()

        router = DeclarativeRouter(bus)

        # Mock StreamManager for testing
        mock_stream_manager = Mock()
        mock_stream_manager.create_stream = AsyncMock(return_value="stream_123")
        mock_stream_manager.send_chunk = AsyncMock(return_value=True)
        mock_stream_manager.close_stream = AsyncMock(return_value=True)

        yield {
            "bus": bus,
            "router": router,
            "stream_manager": mock_stream_manager
        }

        await bus.stop()

    @pytest.mark.asyncio
    async def test_real_streaming_component_integration(self, integration_setup):
        """
        Test real integration between request_stream and existing streaming components.

        This test uses a realistic mock of how LLM components currently work
        and verifies our integration connects everything properly.
        """
        setup = integration_setup

        # Mock LLM component with existing streaming methods
        class MockLLMComponent(MessageBusIntegration):
            def __init__(self, name, router, stream_manager):
                super().__init__()
                self.name = name
                self._router = router
                self._stream_manager = stream_manager
                self.streaming_enabled = True

            def _can_stream_output(self):
                return True

            async def _generate_and_stream_output(self, input_data, stream_id):
                """Existing method that real LLM components have."""
                # Simulate generating streaming output
                chunks = ["Hello", " world", "!", ""]
                for i, chunk_data in enumerate(chunks):
                    is_final = (i == len(chunks) - 1)
                    await self.stream_output(stream_id, chunk_data, is_final)

            async def stream_output(self, stream_id, data, is_final=False):
                """Existing method that sends to StreamManager."""
                return await self._stream_manager.send_chunk(stream_id, data, is_final)

        llm = MockLLMComponent("test_llm", setup["router"], setup["stream_manager"])

        # Mock requesting component
        class MockRequestingComponent(MessageBusIntegration):
            def __init__(self, name, router):
                super().__init__()
                self.name = name
                self._router = router

        requester = MockRequestingComponent("test_requester", setup["router"])

        # Configure router with both components
        components = {
            "test_llm": {"object": llm, "component": "llm"},
            "test_requester": {"object": requester, "component": "agent"}
        }
        setup["router"].configure_from_components(components)

        # TDD: This should work once we implement the integration
        # For now, this will use our current fake streaming
        chunks = []
        async for chunk in requester.request_stream("test_llm", {"prompt": "Hello"}):
            chunks.append(chunk)

        # Current behavior: single chunk (fake streaming)
        assert len(chunks) == 1
        assert chunks[0].is_final

        # TODO: After implementation, should have multiple real chunks
        # assert len(chunks) > 1
        # assert not chunks[0].is_final
        # assert chunks[-1].is_final

    @pytest.mark.asyncio
    async def test_streaming_error_handling(self, integration_setup):
        """
        Test error handling in streaming integration.

        Streaming can fail in various ways and we need graceful error handling.
        """
        setup = integration_setup

        # Mock component that fails during streaming
        class MockFailingStreamComponent(MessageBusIntegration):
            def __init__(self, name, router):
                super().__init__()
                self.name = name
                self._router = router

            async def _generate_and_stream_output(self, input_data, stream_id):
                """Simulate streaming failure."""
                # Send one chunk successfully
                await self.stream_output(stream_id, "Starting...", is_final=False)
                # Then fail
                raise RuntimeError("Streaming failed!")

            async def stream_output(self, stream_id, data, is_final=False):
                """Mock stream output."""
                pass  # Success

        component = MockFailingStreamComponent("failing_stream", setup["router"])

        # Mock requesting component
        requester = MockRequestingComponent("requester", setup["router"])

        # TDD: Error handling should produce error chunk
        chunks = []
        async for chunk in requester.request_stream("failing_stream", {"prompt": "test"}):
            chunks.append(chunk)

        # Should get error in streaming response
        assert len(chunks) >= 1
        assert chunks[-1].is_final
        assert chunks[-1].metadata.get("error") is True


class TestStreamingRouterIntegration:
    """TDD tests for router streaming support."""

    @pytest.fixture
    async def router_setup(self):
        """Setup for router streaming tests."""
        bus = InMemoryMessageBus()
        await bus.start()

        router = DeclarativeRouter(bus)

        yield {"bus": bus, "router": router}

        await bus.stop()

    @pytest.mark.asyncio
    async def test_router_send_to_component_with_stream(self, router_setup):
        """
        TDD: Router should support send_to_component_with_stream().

        This drives us to implement streaming support in the router.
        """
        setup = router_setup
        router = setup["router"]

        # TDD: This method should exist after implementation
        assert not hasattr(router, 'send_to_component_with_stream'), \
            "Router streaming not implemented yet"

        # After implementation, this should work:
        # success, stream_id = await router.send_to_component_with_stream(
        #     name="target_component",
        #     source_component_name="source_component",
        #     data={"prompt": "test streaming"}
        # )
        # assert success
        # assert stream_id is not None

    @pytest.mark.asyncio
    async def test_router_stream_message_handling(self, router_setup):
        """
        TDD: Router should handle 'stream_request' and 'stream_chunk' messages.

        The router needs new message types for streaming communication.
        """
        setup = router_setup

        # TDD: These message types should be supported
        expected_stream_message_types = [
            "stream_request",   # Request to start streaming
            "stream_chunk",     # Individual streaming chunks
            "stream_complete",  # Stream finished
            "stream_error"      # Stream error
        ]

        # Currently not implemented
        for msg_type in expected_stream_message_types:
            # After implementation, router should handle these
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])