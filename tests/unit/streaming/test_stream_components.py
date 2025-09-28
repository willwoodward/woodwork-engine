"""Tests for streaming-enabled components."""

import pytest
from unittest.mock import Mock
from woodwork.components.streaming_mixin import StreamingMixin


class TestStreamingComponents:
    """Test streaming functionality in various component types."""

    def test_streaming_component_configuration(self):
        """Test component with streaming configuration."""

        class TestComponent(StreamingMixin):
            def __init__(self, config=None):
                self.name = "test_component"
                self.config = config or {}
                super().__init__()

        # Component with streaming enabled
        streaming_config = {"streaming": True}
        streaming_component = TestComponent(streaming_config)

        assert streaming_component.streaming_enabled
        assert streaming_component.streaming_input
        assert streaming_component.streaming_output

        # Component without streaming
        non_streaming_component = TestComponent()

        assert not non_streaming_component.streaming_enabled
        assert not non_streaming_component.streaming_input
        assert not non_streaming_component.streaming_output

    def test_streaming_workflow(self):
        """Test basic streaming component workflow."""

        class Producer(StreamingMixin):
            def __init__(self):
                self.name = "producer"
                self.config = {"streaming": True}
                super().__init__()
                self.data_produced = []

            def produce_data(self, data):
                """Simple data production."""
                if self.streaming_output:
                    self.data_produced.append(f"streamed_{data}")
                else:
                    self.data_produced.append(data)

        class Consumer(StreamingMixin):
            def __init__(self):
                self.name = "consumer"
                self.config = {"streaming": True}
                super().__init__()
                self.data_consumed = []

            def consume_data(self, data):
                """Simple data consumption."""
                if self.streaming_input:
                    self.data_consumed.append(f"received_stream_{data}")
                else:
                    self.data_consumed.append(data)

        producer = Producer()
        consumer = Consumer()

        # Test production
        producer.produce_data("test_data")
        assert "streamed_test_data" in producer.data_produced

        # Test consumption
        consumer.consume_data("test_data")
        assert "received_stream_test_data" in consumer.data_consumed

    def test_concurrent_streaming_components(self):
        """Test multiple components with streaming enabled."""

        class StreamingComponent(StreamingMixin):
            def __init__(self, name, streaming_enabled=True):
                self.name = name
                self.config = {"streaming": streaming_enabled}
                super().__init__()
                self.processed_items = []

            def process_item(self, item):
                """Process an item."""
                prefix = "stream_" if self.streaming_enabled else "batch_"
                self.processed_items.append(f"{prefix}{item}")

        # Create multiple streaming components
        components = [
            StreamingComponent("comp1", True),
            StreamingComponent("comp2", True),
            StreamingComponent("comp3", False)
        ]

        # Process items
        for i, comp in enumerate(components):
            comp.process_item(f"item_{i}")

        # Verify streaming behavior
        assert "stream_item_0" in components[0].processed_items
        assert "stream_item_1" in components[1].processed_items
        assert "batch_item_2" in components[2].processed_items

    def test_streaming_memory_management(self):
        """Test that streaming components manage memory properly."""

        class MemoryAwareComponent(StreamingMixin):
            def __init__(self):
                self.name = "memory_component"
                self.config = {"streaming": True}
                super().__init__()
                self.buffer_size = 0

            def add_to_buffer(self, data):
                """Add data to buffer."""
                if self.streaming_enabled:
                    # Streaming mode: smaller buffer
                    self.buffer_size = min(self.buffer_size + len(data), 100)
                else:
                    # Batch mode: larger buffer
                    self.buffer_size += len(data)

        component = MemoryAwareComponent()

        # Add large amount of data
        large_data = "x" * 200
        component.add_to_buffer(large_data)

        # Should be limited in streaming mode
        assert component.buffer_size == 100

    def test_streaming_backpressure_handling(self):
        """Test backpressure handling in streaming components."""

        class BackpressureComponent(StreamingMixin):
            def __init__(self):
                self.name = "backpressure_component"
                self.config = {"streaming": True}
                super().__init__()
                self.queue_size = 0
                self.dropped_items = 0

            def handle_incoming_data(self, data):
                """Handle incoming data with backpressure."""
                if self.streaming_enabled:
                    max_queue = 10
                    if self.queue_size < max_queue:
                        self.queue_size += 1
                        return True  # Accepted
                    else:
                        self.dropped_items += 1
                        return False  # Dropped due to backpressure
                else:
                    self.queue_size += 1
                    return True

        component = BackpressureComponent()

        # Send more data than capacity
        accepted = 0
        for i in range(15):
            if component.handle_incoming_data(f"data_{i}"):
                accepted += 1

        # Should have accepted 10, dropped 5
        assert accepted == 10
        assert component.dropped_items == 5
        assert component.queue_size == 10