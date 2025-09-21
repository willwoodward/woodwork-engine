"""
Test suite for unified event system architecture

This test suite drives the implementation of the unified event system that
eliminates threading issues and provides real-time event delivery.
"""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, Mock, patch
from typing import Dict, Any, List

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from woodwork.types import InputReceivedPayload, AgentThoughtPayload, ToolCallPayload


class TestUnifiedEventBus:
    """Test the UnifiedEventBus that replaces EventManager + DeclarativeRouter + MessageBus"""

    @pytest.fixture
    def event_bus(self):
        """Create a UnifiedEventBus instance for testing"""
        from woodwork.core.unified_event_bus import UnifiedEventBus
        return UnifiedEventBus()

    @pytest.fixture
    def mock_component(self):
        """Create a mock component for testing"""
        component = Mock()
        component.name = "test_component"
        component.input = AsyncMock()
        return component

    async def test_event_bus_creation(self, event_bus):
        """Test that UnifiedEventBus can be created"""
        assert event_bus is not None
        assert hasattr(event_bus, 'emit')
        assert hasattr(event_bus, 'register_component')
        assert hasattr(event_bus, 'register_hook')

    async def test_component_registration(self, event_bus, mock_component):
        """Test that components can be registered with the event bus"""
        # Register component
        event_bus.register_component(mock_component)

        # Verify component is registered
        assert mock_component.name in event_bus._components
        assert event_bus._components[mock_component.name] == mock_component

    async def test_routing_table_configuration(self, event_bus, mock_component):
        """Test that routing table is configured from component 'to' properties"""
        # Mock component with routing configuration
        mock_component.to = "target_component"

        # Register component
        event_bus.register_component(mock_component)
        event_bus.configure_routing()

        # Verify routing table
        assert mock_component.name in event_bus._routing_table
        assert "target_component" in event_bus._routing_table[mock_component.name]

    async def test_hook_registration(self, event_bus):
        """Test that hooks can be registered for events"""
        hook_called = False
        hook_payload = None

        async def test_hook(payload):
            nonlocal hook_called, hook_payload
            hook_called = True
            hook_payload = payload

        # Register hook
        event_bus.register_hook("test.event", test_hook)

        # Emit event
        payload = {"data": "test"}
        await event_bus.emit("test.event", payload)

        # Verify hook was called
        assert hook_called
        assert hook_payload == payload

    async def test_direct_event_emission_without_delays(self, event_bus):
        """Test that events are emitted immediately without thread delays"""
        events_received = []

        async def capture_event(payload):
            events_received.append((time.time(), payload))

        # Register hook
        event_bus.register_hook("input.received", capture_event)

        # Emit event and measure timing
        start_time = time.time()
        payload = InputReceivedPayload(
            input="test input",
            inputs={},
            session_id="test_session",
            component_id="test_component",
            component_type="inputs"
        )
        await event_bus.emit("input.received", payload)

        # Verify immediate delivery (< 10ms)
        assert len(events_received) == 1
        event_time = events_received[0][0]
        delivery_delay = event_time - start_time
        assert delivery_delay < 0.01, f"Event delivery took {delivery_delay:.4f}s, expected < 0.01s"

    async def test_component_to_component_routing(self, event_bus):
        """Test that events are routed between components via 'to' configuration"""
        # Create source and target components
        source_component = Mock()
        source_component.name = "source"
        source_component.to = "target"

        target_component = Mock()
        target_component.name = "target"
        target_component.input = AsyncMock()

        # Register components
        event_bus.register_component(source_component)
        event_bus.register_component(target_component)
        event_bus.configure_routing()

        # Emit event from source
        payload = {"data": "test_routing"}
        await event_bus.emit_from_component("source", "component.output", payload)

        # Verify target component received the event
        target_component.input.assert_called_once()

    async def test_concurrent_hook_processing(self, event_bus):
        """Test that hooks are processed concurrently without blocking"""
        hook1_called = False
        hook2_called = False
        hook1_delay = 0.05  # 50ms delay
        hook2_delay = 0.05  # 50ms delay

        async def slow_hook1(payload):
            nonlocal hook1_called
            await asyncio.sleep(hook1_delay)
            hook1_called = True

        async def slow_hook2(payload):
            nonlocal hook2_called
            await asyncio.sleep(hook2_delay)
            hook2_called = True

        # Register hooks
        event_bus.register_hook("test.event", slow_hook1)
        event_bus.register_hook("test.event", slow_hook2)

        # Emit event and measure total time
        start_time = time.time()
        await event_bus.emit("test.event", {"data": "test"})
        total_time = time.time() - start_time

        # Verify both hooks called and total time is approximately one delay (concurrent)
        assert hook1_called
        assert hook2_called
        assert total_time < (hook1_delay + hook2_delay), f"Hooks not concurrent: {total_time:.3f}s"

    async def test_real_time_websocket_event_delivery(self, event_bus):
        """Test real-time event delivery to WebSocket connections"""
        websocket_events = []

        # Mock WebSocket handler
        async def websocket_handler(payload):
            websocket_events.append((time.time(), payload.event_type if hasattr(payload, 'event_type') else 'unknown'))

        # Register WebSocket as hook subscriber
        event_bus.register_hook("input.received", websocket_handler)
        event_bus.register_hook("agent.thought", websocket_handler)
        event_bus.register_hook("tool.call", websocket_handler)

        # Emit sequence of events
        start_time = time.time()

        await event_bus.emit("input.received", InputReceivedPayload(
            input="test", inputs={}, session_id="test", component_id="input", component_type="inputs"
        ))

        await asyncio.sleep(0.001)  # Minimal delay

        await event_bus.emit("agent.thought", AgentThoughtPayload(
            thought="thinking", component_id="agent", component_type="agents"
        ))

        await asyncio.sleep(0.001)  # Minimal delay

        await event_bus.emit("tool.call", ToolCallPayload(
            tool_name="test_tool", arguments={}, component_id="agent", component_type="agents"
        ))

        # Verify all events received in real-time
        assert len(websocket_events) == 3

        # Verify timing - each event should be delivered immediately
        for i, (event_time, event_type) in enumerate(websocket_events):
            delay_from_start = event_time - start_time
            assert delay_from_start < 0.1, f"Event {i} ({event_type}) delay: {delay_from_start:.4f}s"


class TestAsyncRuntime:
    """Test the AsyncRuntime that replaces distributed startup threading"""

    @pytest.fixture
    def runtime(self):
        """Create an AsyncRuntime instance for testing"""
        from woodwork.core.async_runtime import AsyncRuntime
        return AsyncRuntime()

    @pytest.fixture
    def sample_config(self):
        """Sample component configuration"""
        return {
            "input_comp": {
                "component": "api",
                "type": "inputs",
                "to": "agent_comp"
            },
            "agent_comp": {
                "component": "openai",
                "type": "llms",
                "to": "output_comp"
            },
            "output_comp": {
                "component": "console",
                "type": "outputs"
            }
        }

    async def test_runtime_creation(self, runtime):
        """Test that AsyncRuntime can be created"""
        assert runtime is not None
        assert hasattr(runtime, 'start')
        assert hasattr(runtime, 'event_bus')

    async def test_component_parsing_and_registration(self, runtime, sample_config):
        """Test that components are parsed and registered correctly"""
        # Start runtime with config
        with patch('woodwork.core.async_runtime.parse_components') as mock_parse:
            mock_components = [Mock(name="input_comp"), Mock(name="agent_comp")]
            mock_parse.return_value = mock_components

            await runtime.initialize_components(sample_config)

            # Verify components are registered
            for component in mock_components:
                assert component.name in runtime.event_bus._components

    async def test_single_async_context_execution(self, runtime):
        """Test that all components run in single async context (no threading)"""
        # Verify runtime is fully async
        assert asyncio.iscoroutinefunction(runtime.start)

        # Mock component that records its execution context
        execution_contexts = []

        class TestComponent:
            def __init__(self):
                self.name = "test_component"

            async def input(self, data):
                # Record current event loop
                try:
                    loop = asyncio.get_running_loop()
                    execution_contexts.append(id(loop))
                except RuntimeError:
                    execution_contexts.append(None)
                return "processed"

        component = TestComponent()
        runtime.event_bus.register_component(component)

        # Process input through component
        await runtime.process_component_input(component, "test input")

        # Verify execution happened in same event loop
        current_loop_id = id(asyncio.get_running_loop())
        assert len(execution_contexts) == 1
        assert execution_contexts[0] == current_loop_id

    async def test_api_server_integration(self, runtime):
        """Test that API server starts in same async context"""
        # Mock API component
        api_component = Mock()
        api_component.name = "api_input"
        api_component.__class__.__name__ = "api_input"

        runtime.event_bus.register_component(api_component)

        # Test API server detection
        has_api = runtime.has_api_component()
        assert has_api

    async def test_no_cross_thread_communication(self, runtime):
        """Test that no cross-thread queues or processors are used"""
        # Verify runtime doesn't use threading constructs
        assert not hasattr(runtime, '_cross_thread_queue')
        assert not hasattr(runtime, '_message_bus_thread')
        assert not hasattr(runtime.event_bus, '_cross_thread_event_queue')


class TestUnifiedAPIInput:
    """Test the unified API input component without cross-thread processing"""

    @pytest.fixture
    def api_input_component(self):
        """Create API input component for testing"""
        from woodwork.components.inputs.api_input import api_input
        return api_input()

    async def test_direct_websocket_event_subscription(self, api_input_component):
        """Test that WebSocket subscribes directly to events without queues"""
        websocket_events = []

        # Mock WebSocket
        class MockWebSocket:
            async def send_json(self, data):
                websocket_events.append((time.time(), data))

        websocket = MockWebSocket()

        # Subscribe WebSocket to events
        await api_input_component.setup_websocket_subscription(websocket)

        # Emit events through event bus
        event_bus = api_input_component.event_bus
        await event_bus.emit("agent.thought", {"thought": "test"})
        await event_bus.emit("tool.call", {"tool": "test_tool"})

        # Verify events received immediately
        assert len(websocket_events) >= 2

    async def test_input_processing_without_queues(self, api_input_component):
        """Test that input processing is direct without cross-thread queues"""
        # Verify no queue attributes
        assert not hasattr(api_input_component, '_cross_thread_event_queue')
        assert not hasattr(api_input_component, '_priority_event_queue')

        # Process input directly
        result = await api_input_component.handle_input("test input")

        # Verify input was processed (not queued)
        assert result is not None

    async def test_real_time_event_delivery_to_websocket(self, api_input_component):
        """Integration test for real-time WebSocket event delivery"""
        websocket_events = []
        start_times = []

        class TimestampedWebSocket:
            async def send_json(self, data):
                websocket_events.append((time.time(), data))

        websocket = TimestampedWebSocket()
        await api_input_component.setup_websocket_subscription(websocket)

        # Send input and measure delivery timing
        start_time = time.time()
        start_times.append(start_time)

        await api_input_component.handle_input("test message")

        # Should receive input.received event immediately
        await asyncio.sleep(0.01)  # Small buffer for async processing

        # Verify input.received was delivered in real-time
        input_events = [event for event in websocket_events if 'input.received' in str(event[1])]
        assert len(input_events) > 0

        first_event_time = input_events[0][0]
        delivery_delay = first_event_time - start_time
        assert delivery_delay < 0.05, f"Input event delivery took {delivery_delay:.4f}s"


class TestIntegrationScenarios:
    """Integration tests for complete event flow scenarios"""

    @pytest.fixture
    async def full_system(self):
        """Set up complete system with runtime and components"""
        from woodwork.core.async_runtime import AsyncRuntime

        runtime = AsyncRuntime()

        # Mock components
        input_comp = Mock()
        input_comp.name = "input"
        input_comp.to = "agent"
        input_comp.input = AsyncMock()

        agent_comp = Mock()
        agent_comp.name = "agent"
        agent_comp.to = "output"
        agent_comp.input = AsyncMock()

        output_comp = Mock()
        output_comp.name = "output"
        output_comp.input = AsyncMock()

        # Register components
        runtime.event_bus.register_component(input_comp)
        runtime.event_bus.register_component(agent_comp)
        runtime.event_bus.register_component(output_comp)
        runtime.event_bus.configure_routing()

        return runtime, input_comp, agent_comp, output_comp

    async def test_end_to_end_event_flow(self, full_system):
        """Test complete event flow from input to output"""
        runtime, input_comp, agent_comp, output_comp = full_system

        # Emit input event
        await runtime.event_bus.emit_from_component("input", "input.received", {"input": "test"})

        # Verify agent received input
        agent_comp.input.assert_called()

        # Emit agent response
        await runtime.event_bus.emit_from_component("agent", "agent.response", {"response": "test response"})

        # Verify output received response
        output_comp.input.assert_called()

    async def test_websocket_real_time_scenario(self, full_system):
        """Test real-time WebSocket scenario that was failing before"""
        runtime, input_comp, agent_comp, output_comp = full_system

        websocket_events = []

        # Mock WebSocket receiving all events
        async def websocket_handler(payload):
            websocket_events.append((time.time(), getattr(payload, 'event_type', 'unknown')))

        # Subscribe to all relevant events
        event_types = ["input.received", "agent.thought", "agent.action", "tool.call", "tool.observation", "agent.response"]
        for event_type in event_types:
            runtime.event_bus.register_hook(event_type, websocket_handler)

        # Simulate the problematic scenario: input followed by long-running agent process
        start_time = time.time()

        # 1. Input received (should be immediate)
        await runtime.event_bus.emit("input.received", InputReceivedPayload(
            input="test message", inputs={}, session_id="test", component_id="input", component_type="inputs"
        ))

        # 2. Simulate agent processing (with delays like OpenAI API calls)
        await asyncio.sleep(0.1)  # Simulate API delay

        await runtime.event_bus.emit("agent.thought", AgentThoughtPayload(
            thought="processing", component_id="agent", component_type="agents"
        ))

        await runtime.event_bus.emit("tool.call", ToolCallPayload(
            tool_name="search", arguments={}, component_id="agent", component_type="agents"
        ))

        # Verify input.received arrived first and immediately
        assert len(websocket_events) >= 3

        # First event should be input.received and delivered immediately
        first_event_time, first_event_type = websocket_events[0]
        input_delay = first_event_time - start_time
        assert input_delay < 0.01, f"Input event delayed by {input_delay:.4f}s"

        # Verify events are in correct order
        event_types_received = [event[1] for event in websocket_events]
        # input.received should be first
        assert 'input.received' in str(event_types_received[0])