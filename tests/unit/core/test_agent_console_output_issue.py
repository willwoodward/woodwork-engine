"""Test to reproduce the exact issue: agent responses showing as {}

This test reproduces the exact scenario from the user's logs where:
1. Agent processes input and generates "Final Answer"
2. UnifiedEventBus auto-emits 'agent.response'
3. But no routing logs appear
4. Console shows {}
"""

import pytest
import asyncio
from unittest.mock import Mock
from woodwork.runtime.unified_event_bus import UnifiedEventBus
from woodwork.runtime.message_bus.in_memory_bus import InMemoryMessageBus
from woodwork.types.events import GenericPayload


class TestAgentConsoleOutputIssue:
    """Reproduce and test the agent output issue"""

    @pytest.mark.asyncio
    async def test_agent_without_to_config_has_no_routing(self):
        """Test that agents without 'to' config don't have routing targets"""
        event_bus = UnifiedEventBus()

        # Create agent without 'to' config (simulating real scenario)
        mock_agent = Mock()
        mock_agent.name = "coding_ag"
        mock_agent.type = "agent"
        # Agent doesn't have 'to' attribute
        if hasattr(mock_agent, "to"):
            delattr(mock_agent, "to")

        event_bus.register_component(mock_agent)
        event_bus.configure_routing()

        # Check routing table
        targets = event_bus._routing_table.get("coding_ag", [])

        print(f"\n[TEST] Routing table for 'coding_ag': {targets}")
        print(f"[TEST] Full routing table: {event_bus._routing_table}")

        # This is the problem! Agent has no targets
        if not targets:
            print("[TEST] ❌ ISSUE IDENTIFIED: Agent has no routing targets!")
            print("[TEST] This explains why no routing logs appear and output goes nowhere")

    @pytest.mark.asyncio
    async def test_routing_inference_adds_console_output(self):
        """Test if _infer_routing_patterns adds _console_output for agents"""
        event_bus = UnifiedEventBus()

        # Create agent without explicit output - use spec to prevent auto-creation of attributes
        mock_agent = Mock(spec=["name", "type", "__class__"])
        mock_agent.name = "coding_ag"
        mock_agent.type = "agent"
        # Set __class__ for type inference to work
        mock_agent.__class__ = type("llm", (), {})

        event_bus.register_component(mock_agent)
        event_bus.configure_routing()

        # Check if inference added console output
        targets = event_bus._routing_table.get("coding_ag", [])

        print(f"\n[TEST] After inference, targets: {targets}")

        assert "_console_output" in targets, (
            "Agents without explicit 'to' should be routed to _console_output by inference"
        )

    @pytest.mark.asyncio
    async def test_emit_from_component_without_routing_targets(self):
        """Test what happens when emitting from component with no routing targets"""
        event_bus = UnifiedEventBus()

        # Setup message bus
        message_bus = InMemoryMessageBus()
        await message_bus.start()
        event_bus.set_message_bus(message_bus)

        # Register console handler
        console_called = asyncio.Event()
        received_data = None

        async def console_handler(envelope):
            nonlocal received_data
            received_data = envelope.payload
            console_called.set()

        message_bus.register_component_handler("_console_output", console_handler)

        # Create agent WITHOUT routing - use spec to prevent auto-creation
        mock_agent = Mock(spec=["name", "__class__"])
        mock_agent.name = "coding_ag"
        mock_agent.__class__ = type("llm", (), {})

        event_bus.register_component(mock_agent)
        event_bus.configure_routing()

        print(f"\n[TEST] Routing table: {event_bus._routing_table}")

        # Emit agent.response
        payload = GenericPayload(
            component_id="coding_ag",
            component_type="agent",
            data={"response": "Final Answer: Test response", "source_component": "coding_ag"},
        )

        await event_bus.emit_from_component("coding_ag", "agent.response", payload)

        # Wait briefly to see if handler is called
        try:
            await asyncio.wait_for(console_called.wait(), timeout=0.5)
            print("[TEST] ✓ Console handler was called")
            print(f"[TEST] Received data: {received_data}")
        except asyncio.TimeoutError:
            print("[TEST] ❌ Console handler was NOT called within timeout")
            print("[TEST] This reproduces the issue!")

        await message_bus.stop()

        # This assertion should fail, identifying the issue
        assert received_data is not None, "Console handler should have received the agent response"

    @pytest.mark.asyncio
    async def test_full_scenario_with_manual_routing(self):
        """Test the same scenario but WITH manual routing to prove the fix works"""
        event_bus = UnifiedEventBus()

        # Setup message bus
        message_bus = InMemoryMessageBus()
        await message_bus.start()
        event_bus.set_message_bus(message_bus)

        # Register console handler
        console_called = asyncio.Event()
        received_data = None

        async def console_handler(envelope):
            nonlocal received_data
            received_data = envelope.payload
            console_called.set()

        message_bus.register_component_handler("_console_output", console_handler)

        # Create agent WITH routing to console
        mock_agent = Mock()
        mock_agent.name = "coding_ag"
        mock_agent.to = ["_console_output"]  # Explicitly set routing

        event_bus.register_component(mock_agent)
        event_bus.configure_routing()

        print(f"\n[TEST] Routing table with manual routing: {event_bus._routing_table}")

        # Emit agent.response
        payload = GenericPayload(
            component_id="coding_ag",
            component_type="agent",
            data={"response": "Final Answer: Test response", "source_component": "coding_ag"},
        )

        await event_bus.emit_from_component("coding_ag", "agent.response", payload)

        # Wait for handler
        await asyncio.wait_for(console_called.wait(), timeout=1.0)

        await message_bus.stop()

        # This should pass
        assert received_data is not None
        print("[TEST] ✓ With explicit routing, console handler receives the data")

    def test_check_infer_routing_patterns_method(self):
        """Check if _infer_routing_patterns exists and what it does"""
        event_bus = UnifiedEventBus()

        # Check if method exists
        assert hasattr(event_bus, "_infer_routing_patterns"), (
            "UnifiedEventBus should have _infer_routing_patterns method"
        )

        # Create agent without routing
        mock_agent = Mock()
        mock_agent.name = "coding_ag"
        mock_agent.type = "agent"
        if hasattr(mock_agent, "to"):
            delattr(mock_agent, "to")

        event_bus.register_component(mock_agent)

        # Manually call inference
        event_bus._infer_routing_patterns()

        # Check if console output was added
        targets = event_bus._routing_table.get("coding_ag", [])

        print(f"\n[TEST] After manual _infer_routing_patterns call: {targets}")
        print(f"[TEST] Full routing table: {event_bus._routing_table}")

        # Document what we found
        if "_console_output" in targets:
            print("[TEST] ✓ Inference correctly adds _console_output for agents")
        else:
            print("[TEST] ❌ Inference does NOT add _console_output for agents")
            print("[TEST] This is the root cause of the issue!")
