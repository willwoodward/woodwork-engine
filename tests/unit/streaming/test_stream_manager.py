"""Tests for StreamManager component."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from woodwork.core.stream_manager import StreamManager
from woodwork.core.simple_message_bus import SimpleMessageBus
from woodwork.types.streaming_data import StreamDataType


class TestStreamManager:
    """Test suite for StreamManager."""

    @pytest.fixture
    def mock_message_bus(self):
        """Create a mock message bus."""
        bus = Mock(spec=SimpleMessageBus)
        bus.subscribe = Mock()
        return bus

    @pytest.fixture
    def stream_manager(self, mock_message_bus):
        """Create a StreamManager instance."""
        return StreamManager(mock_message_bus)

    def test_initialization(self, stream_manager, mock_message_bus):
        """Test stream manager initializes correctly."""
        assert stream_manager.message_bus == mock_message_bus
        assert stream_manager.active_streams == {}
        assert stream_manager.stream_buffers == {}
        assert stream_manager.stats["streams_created"] == 0
        assert not stream_manager._running

    async def test_start_stop(self, stream_manager):
        """Test starting and stopping the stream manager."""
        # Test start
        await stream_manager.start()
        assert stream_manager._running
        assert stream_manager._cleanup_task is not None

        # Test stop
        await stream_manager.stop()
        assert not stream_manager._running

    async def test_create_stream(self, stream_manager):
        """Test creating a new stream."""
        await stream_manager.start()

        stream_id = await stream_manager.create_stream(
            session_id="test_session",
            component_source="test_source",
            component_target="test_target",
            data_type=StreamDataType.TEXT
        )

        assert stream_id is not None
        assert stream_id in stream_manager.active_streams
        assert stream_manager.stats["streams_created"] == 1

        await stream_manager.stop()

    async def test_list_active_streams(self, stream_manager):
        """Test listing active streams."""
        await stream_manager.start()

        # Initially no streams
        streams = stream_manager.list_active_streams()
        assert len(streams) == 0

        # Create a stream
        stream_id = await stream_manager.create_stream(
            session_id="test_session",
            component_source="test_source",
            component_target="test_target",
            data_type=StreamDataType.TEXT
        )

        # Should now have one stream
        streams = stream_manager.list_active_streams()
        assert len(streams) == 1
        assert stream_id in streams

        await stream_manager.stop()

    async def test_get_stats(self, stream_manager):
        """Test getting stream manager stats."""
        stats = stream_manager.get_stats()

        assert "streams_created" in stats
        assert "chunks_sent" in stats
        assert "chunks_received" in stats
        assert isinstance(stats["streams_created"], int)

    def test_message_bus_integration(self, stream_manager, mock_message_bus):
        """Test that stream manager sets up message bus handlers."""
        # Verify that subscribe was called for expected events
        expected_calls = [
            "stream.chunk",
            "stream.created",
            "stream.completed",
            "stream.failed"
        ]

        subscribe_calls = [call[0][0] for call in mock_message_bus.subscribe.call_args_list]
        for expected_event in expected_calls:
            assert expected_event in subscribe_calls


class TestStreamManagerErrorHandling:
    """Test error handling in StreamManager."""

    @pytest.fixture
    def mock_message_bus(self):
        bus = Mock(spec=SimpleMessageBus)
        bus.subscribe = Mock()
        return bus

    @pytest.fixture
    def stream_manager(self, mock_message_bus):
        return StreamManager(mock_message_bus)

    async def test_duplicate_start_call(self, stream_manager):
        """Test that calling start multiple times is safe."""
        await stream_manager.start()
        first_task = stream_manager._cleanup_task

        # Starting again should not create a new task
        await stream_manager.start()
        assert stream_manager._cleanup_task == first_task

        await stream_manager.stop()

    async def test_stop_without_start(self, stream_manager):
        """Test that stopping without starting is safe."""
        # Should not raise an exception
        await stream_manager.stop()
        assert not stream_manager._running