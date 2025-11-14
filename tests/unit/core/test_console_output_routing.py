"""Unit tests for console output routing via message bus.

This test suite identifies the issue where agent responses are routed to
_console_output but the handler is never invoked, resulting in {} output.
"""

import pytest
import asyncio
from dataclasses import asdict
from unittest.mock import Mock, patch, AsyncMock
from woodwork.core.unified_event_bus import UnifiedEventBus
from woodwork.types.events import GenericPayload
from woodwork.core.message_bus.interface import MessageEnvelope


class TestConsoleOutputRouting:
    """Test that messages to _console_output are properly delivered via message bus"""

    @pytest.mark.asyncio
    async def test_deliver_to_virtual_component_uses_message_bus(self):
        """Test that delivery to virtual components uses message bus"""
        # Setup
        event_bus = UnifiedEventBus()
        mock_message_bus = AsyncMock()
        mock_message_bus.send_to_component = AsyncMock(return_value=True)
        event_bus.set_message_bus(mock_message_bus)

        # Create payload
        payload = GenericPayload(
            component_id="coding_ag",
            component_type="agent",
            data={"response": "Test response", "source_component": "coding_ag"},
        )

        # Execute: deliver to virtual component _console_output
        await event_bus._deliver_to_component(
            target_name="_console_output", event_type="agent.response", payload=payload, source_component="coding_ag"
        )

        # Assert: message bus send_to_component should be called
        mock_message_bus.send_to_component.assert_called_once()

        # Verify envelope was created correctly
        call_args = mock_message_bus.send_to_component.call_args
        envelope = call_args[0][0]
        assert isinstance(envelope, MessageEnvelope)
        assert envelope.target_component == "_console_output"
        assert envelope.event_type == "agent.response"
        assert envelope.sender_component == "coding_ag"
        assert envelope.payload == asdict(payload)

    @pytest.mark.asyncio
    async def test_deliver_to_virtual_component_without_message_bus(self):
        """Test that delivery to virtual component without message bus returns None"""
        # Setup
        event_bus = UnifiedEventBus()
        # Don't set message bus

        payload = GenericPayload(component_id="coding_ag", component_type="agent", data={"response": "Test response"})

        # Execute
        result = await event_bus._deliver_to_component(
            target_name="_console_output", event_type="agent.response", payload=payload, source_component="coding_ag"
        )

        # Assert: should return None without crashing
        assert result is None

    @pytest.mark.asyncio
    async def test_emit_from_component_routes_to_console(self):
        """Test that emitting agent.response routes to _console_output"""
        # Setup
        event_bus = UnifiedEventBus()
        mock_message_bus = AsyncMock()
        mock_message_bus.send_to_component = AsyncMock(return_value=True)
        event_bus.set_message_bus(mock_message_bus)

        # Register a component with routing to _console_output
        mock_agent = Mock()
        mock_agent.name = "coding_ag"
        mock_agent.type = "agent"
        # Add the 'to' config that should route to console
        mock_agent.config = {"to": ["_console_output"]}
        mock_agent.to = ["_console_output"]

        event_bus.register_component(mock_agent)
        event_bus.configure_routing()

        # Create response payload
        payload = GenericPayload(
            component_id="coding_ag",
            component_type="agent",
            data={"response": "Test agent response", "source_component": "coding_ag"},
        )

        # Execute: emit agent.response from the agent
        await event_bus.emit_from_component("coding_ag", "agent.response", payload)

        # Assert: message bus should receive the delivery
        mock_message_bus.send_to_component.assert_called_once()

    @pytest.mark.asyncio
    async def test_console_handler_receives_message(self):
        """Integration test: console handler should be invoked when message is delivered"""
        # This tests the full flow from unified event bus through message bus to handler
        from woodwork.core.message_bus.in_memory_bus import InMemoryMessageBus

        # Setup
        event_bus = UnifiedEventBus()
        message_bus = InMemoryMessageBus()
        await message_bus.start()

        event_bus.set_message_bus(message_bus)

        # Register console handler
        handler_called = asyncio.Event()
        received_envelope = None

        async def mock_console_handler(envelope):
            nonlocal received_envelope
            received_envelope = envelope
            handler_called.set()

        message_bus.register_component_handler("_console_output", mock_console_handler)

        # Setup routing
        mock_agent = Mock()
        mock_agent.name = "coding_ag"
        mock_agent.to = ["_console_output"]
        event_bus.register_component(mock_agent)
        event_bus.configure_routing()

        # Create payload
        payload = GenericPayload(
            component_id="coding_ag", component_type="agent", data={"response": "Test response from agent"}
        )

        # Execute: emit agent.response
        await event_bus.emit_from_component("coding_ag", "agent.response", payload)

        # Wait for handler to be called
        try:
            await asyncio.wait_for(handler_called.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            pytest.fail("Console handler was not called within timeout")

        # Assert: handler received the envelope
        assert received_envelope is not None
        assert received_envelope.target_component == "_console_output"
        assert received_envelope.event_type == "agent.response"
        assert received_envelope.payload == asdict(payload)

        # Cleanup
        await message_bus.stop()

    @pytest.mark.asyncio
    async def test_console_handler_processes_response_data(self):
        """Test that console handler correctly processes response data from payload"""
        from woodwork.core.message_bus.integration import GlobalMessageBusManager

        # Setup
        manager = GlobalMessageBusManager()

        # Create envelope with response data
        payload = GenericPayload(
            component_id="coding_ag",
            component_type="agent",
            data={"response": "This is the agent response that should be displayed", "source_component": "coding_ag"},
        )

        envelope = MessageEnvelope(
            message_id="test-msg-123",
            session_id="test_session",
            event_type="agent.response",
            payload=payload,
            sender_component="coding_ag",
            target_component="_console_output",
        )

        # Capture print output
        printed_output = []
        original_print = print

        def mock_print(text):
            printed_output.append(text)
            original_print(f"[TEST] Captured print: {text}")

        # Execute with mocked print
        with patch("builtins.print", mock_print):
            await manager._handle_console_message(envelope)

        # Assert: the response should be printed
        assert len(printed_output) > 0
        assert "This is the agent response that should be displayed" in printed_output[0]


class TestMessageBusComponentHandlerInvocation:
    """Test that message bus properly invokes registered component handlers"""

    @pytest.mark.asyncio
    async def test_send_to_component_invokes_handler(self):
        """Test that send_to_component calls the registered handler"""
        from woodwork.core.message_bus.in_memory_bus import InMemoryMessageBus

        # Setup
        message_bus = InMemoryMessageBus()
        await message_bus.start()

        handler_called = asyncio.Event()
        received_envelope = None

        async def test_handler(envelope):
            nonlocal received_envelope
            received_envelope = envelope
            handler_called.set()

        # Register handler
        message_bus.register_component_handler("test_component", test_handler)

        # Create envelope
        payload = GenericPayload(component_id="sender", component_type="agent", data={"test": "data"})

        envelope = MessageEnvelope(
            message_id="test-msg-456",
            session_id="test",
            event_type="test.event",
            payload=payload,
            sender_component="sender",
            target_component="test_component",
        )

        # Execute
        success = await message_bus.send_to_component(envelope)

        # Assert
        assert success is True
        await asyncio.wait_for(handler_called.wait(), timeout=1.0)
        assert received_envelope is not None
        assert received_envelope.target_component == "test_component"

        # Cleanup
        await message_bus.stop()


class TestRoutingConfiguration:
    """Test that routing is properly configured for console output"""

    def test_agent_without_explicit_to_gets_console_routing(self):
        """Test that agents without 'to' config get routed to _console_output"""
        event_bus = UnifiedEventBus()

        # Create agent without explicit 'to' config
        mock_agent = Mock()
        mock_agent.name = "coding_ag"
        mock_agent.type = "agent"
        mock_agent.config = {}
        # Simulate that 'to' attribute doesn't exist
        del mock_agent.to

        event_bus.register_component(mock_agent)
        event_bus.configure_routing()

        # Check if agent has console output in routing table
        targets = event_bus._routing_table.get("coding_ag", [])

        # This test documents expected behavior - agents should route to console
        # if they don't have explicit output targets
        assert "_console_output" in targets or len(targets) > 0

    def test_routing_table_includes_console_output(self):
        """Test that _console_output is in routing table for agents"""
        event_bus = UnifiedEventBus()

        mock_agent = Mock()
        mock_agent.name = "coding_ag"
        mock_agent.to = ["_console_output"]

        event_bus.register_component(mock_agent)
        event_bus.configure_routing()

        targets = event_bus._routing_table.get("coding_ag", [])
        assert "_console_output" in targets
