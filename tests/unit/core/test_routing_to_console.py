"""Test to identify why _console_output routing doesn't trigger message bus delivery"""

import pytest
import asyncio
from unittest.mock import Mock
from woodwork.core.unified_event_bus import UnifiedEventBus, get_global_event_bus
from woodwork.core.message_bus.in_memory_bus import InMemoryMessageBus
from woodwork.core.message_bus.integration import GlobalMessageBusManager, get_global_message_bus
from woodwork.types.events import GenericPayload


class TestRoutingToConsole:
    """Identify the specific issue preventing console output delivery"""

    @pytest.mark.asyncio
    async def test_message_bus_is_set_on_unified_event_bus(self):
        """Check if message bus is properly set on unified event bus"""
        # Simulate real initialization flow
        manager = GlobalMessageBusManager()

        # Create mock components
        component_configs = {
            "coding_ag": {
                "object": Mock(name="coding_ag", to=["_console_output"])
            }
        }

        # Initialize (this should set message bus on unified event bus)
        await manager.initialize(component_configs)

        # Get the unified event bus
        event_bus = manager.router

        # Check if message bus is set
        print(f"\n[TEST] event_bus._message_bus: {event_bus._message_bus}")
        print(f"[TEST] type: {type(event_bus._message_bus)}")

        assert event_bus._message_bus is not None, \
            "Message bus should be set on unified event bus"

        # Check routing table
        print(f"[TEST] Routing table: {event_bus._routing_table}")

        # Try emitting an event
        payload = GenericPayload(
            component_id="coding_ag",
            component_type="agent",
            data={"response": "Test response"}
        )

        # Check if console handler is registered
        if hasattr(manager.message_bus, 'component_handlers'):
            print(f"[TEST] Registered component handlers: {list(manager.message_bus.component_handlers.keys())}")

        await event_bus.emit_from_component("coding_ag", "agent.response", payload)

        # Give it a moment to process
        await asyncio.sleep(0.1)

    @pytest.mark.asyncio
    async def test_direct_message_bus_delivery(self):
        """Test message bus delivery directly"""
        # Setup message bus
        message_bus = InMemoryMessageBus()
        await message_bus.start()

        # Register console handler
        handler_called = asyncio.Event()
        received_payload = None

        async def console_handler(envelope):
            nonlocal received_payload
            received_payload = envelope.payload
            handler_called.set()
            print(f"[TEST] Console handler called with payload: {envelope.payload}")

        message_bus.register_component_handler("_console_output", console_handler)

        # Create envelope
        from woodwork.core.message_bus.interface import MessageEnvelope
        import uuid

        payload = GenericPayload(
            component_id="coding_ag",
            component_type="agent",
            data={"response": "Test response"}
        )

        envelope = MessageEnvelope(
            message_id=f"msg-{uuid.uuid4().hex[:12]}",
            session_id="test",
            event_type="agent.response",
            payload=payload,
            sender_component="coding_ag",
            target_component="_console_output"
        )

        print(f"\n[TEST] Sending envelope to _console_output")
        success = await message_bus.send_to_component(envelope)
        print(f"[TEST] send_to_component returned: {success}")

        # Wait for handler
        try:
            await asyncio.wait_for(handler_called.wait(), timeout=1.0)
            print(f"[TEST] Handler was called successfully")
        except asyncio.TimeoutError:
            print(f"[TEST] Handler was NOT called!")

        await message_bus.stop()

        assert received_payload is not None

    @pytest.mark.asyncio
    async def test_unified_event_bus_deliver_to_component_logs(self):
        """Test what logs appear when delivering to _console_output"""
        import logging

        # Enable DEBUG logging to see all logs
        logging.basicConfig(level=logging.DEBUG)

        # Setup
        event_bus = UnifiedEventBus()
        message_bus = InMemoryMessageBus()
        await message_bus.start()
        event_bus.set_message_bus(message_bus)

        # Register console handler
        async def console_handler(envelope):
            print(f"[TEST] Console handler called!")

        message_bus.register_component_handler("_console_output", console_handler)

        # Register agent
        mock_agent = Mock()
        mock_agent.name = "coding_ag"
        mock_agent.to = ["_console_output"]

        event_bus.register_component(mock_agent)
        event_bus.configure_routing()

        print(f"\n[TEST] Components in registry: {list(event_bus._components.keys())}")
        print(f"[TEST] Routing table: {event_bus._routing_table}")
        print(f"[TEST] Message bus set: {event_bus._message_bus is not None}")

        # Emit event
        payload = GenericPayload(
            component_id="coding_ag",
            component_type="agent",
            data={"response": "Test response"}
        )

        print(f"\n[TEST] About to emit agent.response from coding_ag...")
        await event_bus.emit_from_component("coding_ag", "agent.response", payload)
        print(f"[TEST] Emit complete")

        await asyncio.sleep(0.1)
        await message_bus.stop()
