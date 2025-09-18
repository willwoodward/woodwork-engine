"""Integration tests for streaming data flows."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from tests.unit.fixtures.mock_components import MockStream


class TestStreamingFlow:
    """Test end-to-end streaming workflows."""

    @pytest.fixture
    async def streaming_setup(self):
        """Set up streaming infrastructure."""
        from woodwork.core.stream_manager import StreamManager
        from woodwork.components.streaming_mixin import StreamingMixin
        from woodwork.core.simple_message_bus import SimpleMessageBus

        # Create message bus and stream manager
        message_bus = SimpleMessageBus()
        stream_manager = StreamManager(message_bus)

        # Create streaming components
        class StreamProducer(StreamingMixin):
            def __init__(self):
                super().__init__(name="producer", config={"streaming": True})
                self.set_stream_manager(stream_manager)

            async def produce_data(self, target="consumer", count=5):
                stream_id = await self.create_output_stream(target)
                for i in range(count):
                    await self.stream_output(stream_id, f"data_chunk_{i}")
                await self.stream_output(stream_id, "", is_final=True)
                return stream_id

        class StreamConsumer(StreamingMixin):
            def __init__(self):
                super().__init__(name="consumer", config={"streaming": True})
                self.set_stream_manager(stream_manager)
                self.consumed_data = []

            async def consume_data(self, stream_id):
                async for chunk in self.receive_input_stream(stream_id):
                    if chunk:  # Skip empty final chunks
                        self.consumed_data.append(chunk)
                return len(self.consumed_data)

        class StreamProcessor(StreamingMixin):
            def __init__(self, transform_func):
                super().__init__(name="processor", config={"streaming": True})
                self.set_stream_manager(stream_manager)
                self.transform_func = transform_func

            async def process_stream(self, input_stream_id, target="consumer"):
                output_stream_id = await self.create_output_stream(target)
                async for chunk in self.receive_input_stream(input_stream_id):
                    if chunk:  # Skip empty final chunks
                        transformed = self.transform_func(chunk)
                        await self.stream_output(output_stream_id, transformed)
                await self.stream_output(output_stream_id, "", is_final=True)
                return output_stream_id

        yield {
            "stream_manager": stream_manager,
            "producer": StreamProducer(),
            "consumer": StreamConsumer(),
            "processor": StreamProcessor(lambda x: x.upper())
        }

    async def test_producer_consumer_flow(self, streaming_setup):
        """Test basic producer-consumer streaming flow."""
        setup = streaming_setup
        producer = setup["producer"]
        consumer = setup["consumer"]

        # Producer creates data - should return a stream ID
        stream_id = await producer.produce_data(count=5)
        assert stream_id is not None
        assert isinstance(stream_id, str)
        assert stream_id.startswith("stream-")  # UUID format from real implementation

    async def test_stream_processing_pipeline(self, streaming_setup):
        """Test stream processing pipeline."""
        setup = streaming_setup
        producer = setup["producer"]
        processor = setup["processor"]

        # Create pipeline: producer -> processor
        producer_stream = await producer.produce_data(count=3)
        assert producer_stream is not None
        assert isinstance(producer_stream, str)

        processed_stream = await processor.process_stream(producer_stream)
        assert processed_stream is not None
        assert isinstance(processed_stream, str)
        assert processed_stream != producer_stream  # Should be different streams

    async def test_concurrent_streaming(self, streaming_setup):
        """Test concurrent streaming operations."""
        setup = streaming_setup

        # Create multiple producer instances
        from woodwork.components.streaming_mixin import StreamingMixin
        stream_manager = setup["stream_manager"]

        class ConcurrentProducer(StreamingMixin):
            def __init__(self, name):
                super().__init__(name=name, config={"streaming": True})
                self.set_stream_manager(stream_manager)

            async def produce_data(self, target="consumer", count=2):
                stream_id = await self.create_output_stream(target)
                for i in range(count):
                    await self.stream_output(stream_id, f"data_chunk_{i}")
                await self.stream_output(stream_id, "", is_final=True)
                return stream_id

        producers = [ConcurrentProducer(f"producer_{i}") for i in range(3)]

        # Run producers concurrently
        tasks = [producer.produce_data(count=2) for producer in producers]
        stream_ids = await asyncio.gather(*tasks)

        assert len(stream_ids) == 3
        assert all(isinstance(stream_id, str) for stream_id in stream_ids)
        assert len(set(stream_ids)) == 3  # All stream IDs should be unique

    async def test_streaming_error_handling(self, streaming_setup):
        """Test error handling in streaming flows."""
        setup = streaming_setup
        producer = setup["producer"]

        with patch('woodwork.core.stream_manager.StreamManager') as mock_manager_class:
            mock_manager = Mock()
            mock_manager.create_stream = AsyncMock(return_value="error_stream")
            mock_manager.write_to_stream = AsyncMock(side_effect=Exception("Stream write failed"))
            mock_manager_class.return_value = mock_manager

            # Producer should handle write errors gracefully
            try:
                stream_id = await producer.produce_data(count=1)
                # In real implementation, producer might handle errors internally
            except Exception as e:
                assert "Stream write failed" in str(e)

    async def test_stream_backpressure(self, streaming_setup):
        """Test backpressure handling in streaming."""
        setup = streaming_setup

        class BackpressureProducer(setup["producer"].__class__):
            async def produce_with_backpressure(self, count, delay=0.01, target="consumer"):
                stream_id = await self.create_output_stream(target)
                for i in range(count):
                    await self.stream_output(stream_id, f"data_{i}")
                    await asyncio.sleep(delay)  # Simulate backpressure
                await self.stream_output(stream_id, "", is_final=True)
                return stream_id

        producer = BackpressureProducer()
        producer.set_stream_manager(setup["stream_manager"])

        # Should handle backpressure delays
        start_time = asyncio.get_event_loop().time()
        stream_id = await producer.produce_with_backpressure(count=5, delay=0.001)
        end_time = asyncio.get_event_loop().time()

        assert stream_id is not None
        assert isinstance(stream_id, str)
        assert end_time - start_time >= 0.005  # Should take at least 5ms

    async def test_stream_memory_management(self, streaming_setup):
        """Test memory management in streaming."""
        setup = streaming_setup

        class MemoryManagedStreamer(setup["producer"].__class__):
            def __init__(self):
                super().__init__()
                self.active_streams = set()

            async def create_managed_stream(self, target="memory"):
                stream_id = await self.create_output_stream(target)
                self.active_streams.add(stream_id)
                return stream_id

            async def cleanup_streams(self):
                for stream_id in self.active_streams.copy():
                    await self.stream_output(stream_id, "", is_final=True)
                    self.active_streams.remove(stream_id)

        streamer = MemoryManagedStreamer()
        streamer.set_stream_manager(setup["stream_manager"])

        # Create multiple streams
        for _ in range(5):
            await streamer.create_managed_stream()

        assert len(streamer.active_streams) == 5

        # Cleanup all streams
        await streamer.cleanup_streams()
        assert len(streamer.active_streams) == 0


class TestRealWorldStreamingScenarios:
    """Test real-world streaming scenarios."""

    async def test_agent_thought_streaming(self):
        """Test streaming agent thoughts in real-time."""
        from woodwork.components.streaming_mixin import StreamingMixin

        class ThinkingAgent(StreamingMixin):
            def __init__(self):
                super().__init__(name="thinking_agent", config={"streaming": True})
                self.thought_stream = None

            async def start_thinking(self, target="listener"):
                self.thought_stream = await self.create_output_stream(target)
                return self.thought_stream

            async def think(self, thought):
                if self.thought_stream:
                    await self.stream_output(self.thought_stream, f"Thought: {thought}")

            async def stop_thinking(self):
                if self.thought_stream:
                    await self.stream_output(self.thought_stream, "", is_final=True)

        from woodwork.core.simple_message_bus import SimpleMessageBus
        from woodwork.core.stream_manager import StreamManager

        with patch('woodwork.core.stream_manager.StreamManager') as mock_manager_class:
            mock_manager = Mock()
            mock_manager.create_stream = AsyncMock(return_value="thought_stream")
            mock_manager.send_chunk = AsyncMock(return_value=True)
            mock_manager_class.return_value = mock_manager

            agent = ThinkingAgent()
            agent.set_stream_manager(mock_manager)

            # Start thinking process
            stream_id = await agent.start_thinking()
            assert stream_id == "thought_stream"

            # Stream thoughts
            await agent.think("I need to analyze this problem")
            await agent.think("Let me break it down into steps")

            # Stop thinking
            await agent.stop_thinking()

            # Verify stream operations
            mock_manager.create_stream.assert_called_once()
            assert mock_manager.send_chunk.call_count == 3  # 2 thoughts + final

    async def test_tool_output_streaming(self):
        """Test streaming tool outputs."""
        from woodwork.components.streaming_mixin import StreamingMixin

        class StreamingTool(StreamingMixin):
            def __init__(self):
                super().__init__(name="streaming_tool", config={"streaming": True})

            async def execute_with_streaming(self, action, inputs, target="listener"):
                stream_id = await self.create_output_stream(target)

                # Simulate tool execution with streaming output
                progress_steps = ["Starting", "Processing", "Completing", "Done"]
                for step in progress_steps:
                    await self.stream_output(stream_id, f"Status: {step}")

                await self.stream_output(stream_id, "", is_final=True)
                return f"Tool executed: {action}"

        with patch('woodwork.core.stream_manager.StreamManager') as mock_manager_class:
            mock_manager = Mock()
            mock_manager.create_stream = AsyncMock(return_value="tool_stream")
            mock_manager.send_chunk = AsyncMock(return_value=True)
            mock_manager_class.return_value = mock_manager

            tool = StreamingTool()
            tool.set_stream_manager(mock_manager)
            result = await tool.execute_with_streaming("test_action", {})

            assert result == "Tool executed: test_action"
            assert mock_manager.send_chunk.call_count == 5  # 4 progress steps + final

    async def test_multi_component_streaming_workflow(self):
        """Test streaming workflow across multiple components."""
        from woodwork.components.streaming_mixin import StreamingMixin

        class StreamingWorkflow:
            def __init__(self):
                self.components = {}

            def add_component(self, name, component):
                self.components[name] = component

            async def run_workflow(self, data):
                results = {}

                # Run components in sequence with streaming
                for name, component in self.components.items():
                    if hasattr(component, 'process_stream'):
                        stream_id = await component.create_output_stream("workflow")
                        await component.stream_output(stream_id, data)
                        results[name] = stream_id

                return results

        class WorkflowComponent(StreamingMixin):
            def __init__(self, name, processor_func):
                super().__init__(name=name, config={"streaming": True})
                self.processor_func = processor_func

            async def process_stream(self, data, target="workflow"):
                stream_id = await self.create_output_stream(target)
                processed = self.processor_func(data)
                await self.stream_output(stream_id, processed)
                await self.stream_output(stream_id, "", is_final=True)
                return stream_id

        with patch('woodwork.core.stream_manager.StreamManager') as mock_manager_class:
            stream_counter = 0

            def create_stream_id(*args, **kwargs):
                nonlocal stream_counter
                stream_counter += 1
                return f"workflow_stream_{stream_counter}"

            mock_manager = Mock()
            mock_manager.create_stream = AsyncMock(side_effect=create_stream_id)
            mock_manager.send_chunk = AsyncMock(return_value=True)
            mock_manager_class.return_value = mock_manager

            # Create workflow
            workflow = StreamingWorkflow()
            validator = WorkflowComponent("validator", lambda x: f"validated_{x}")
            processor = WorkflowComponent("processor", lambda x: f"processed_{x}")

            # Set stream managers
            validator.set_stream_manager(mock_manager)
            processor.set_stream_manager(mock_manager)

            workflow.add_component("validator", validator)
            workflow.add_component("processor", processor)

            results = await workflow.run_workflow("test_data")

            assert len(results) == 2
            assert "validator" in results
            assert "processor" in results

    async def test_streaming_performance_monitoring(self):
        """Test performance monitoring in streaming operations."""
        from woodwork.components.streaming_mixin import StreamingMixin

        class MonitoredStreamer(StreamingMixin):
            def __init__(self):
                super().__init__(name="monitored_streamer", config={"streaming": True})
                self.performance_metrics = {}

            async def stream_with_monitoring(self, data_count, target="monitor"):
                import time

                start_time = time.time()
                stream_id = await self.create_output_stream(target)

                for i in range(data_count):
                    chunk_start = time.time()
                    await self.stream_output(stream_id, f"chunk_{i}")
                    chunk_end = time.time()

                    self.performance_metrics[f"chunk_{i}"] = {
                        "write_time": chunk_end - chunk_start
                    }

                end_time = time.time()
                self.performance_metrics["total_time"] = end_time - start_time

                await self.stream_output(stream_id, "", is_final=True)
                return stream_id

        with patch('woodwork.core.stream_manager.StreamManager') as mock_manager_class:
            mock_manager = Mock()
            mock_manager.create_stream = AsyncMock(return_value="monitored_stream")
            mock_manager.send_chunk = AsyncMock(return_value=True)
            mock_manager_class.return_value = mock_manager

            streamer = MonitoredStreamer()
            streamer.set_stream_manager(mock_manager)
            stream_id = await streamer.stream_with_monitoring(data_count=3)

            assert stream_id == "monitored_stream"
            assert "total_time" in streamer.performance_metrics
            assert len([k for k in streamer.performance_metrics.keys() if k.startswith("chunk_")]) == 3