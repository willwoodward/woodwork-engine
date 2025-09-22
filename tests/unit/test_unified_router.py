"""
Comprehensive tests for UnifiedEventBus routing functionality.

Tests all routing features including target extraction, routing table configuration,
component-to-component routing, message bus compatibility, and edge cases.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from woodwork.core.unified_event_bus import UnifiedEventBus
from woodwork.types import InputReceivedPayload, AgentThoughtPayload


class TestUnifiedEventBusRouting:
    """Test suite for UnifiedEventBus routing functionality."""

    @pytest.fixture
    def router(self):
        """Create UnifiedEventBus for routing tests."""
        return UnifiedEventBus()

    @pytest.fixture
    def mock_components(self):
        """Create mock components with different routing configurations."""
        components = {}

        # Component with string target
        comp1 = Mock()
        comp1.name = "input"
        comp1.to = "agent"
        components["input"] = comp1

        # Component with list targets
        comp2 = Mock()
        comp2.name = "agent"
        comp2.to = ["tool1", "tool2", "output"]
        components["agent"] = comp2

        # Component with _output property (like api_input)
        comp3 = Mock()
        comp3.name = "api_input"
        comp3._output = "coding_agent"
        # Remove auto-created 'to' attribute to test _output fallback
        del comp3.to
        components["api_input"] = comp3

        # Component with output_targets property
        comp4 = Mock()
        comp4.name = "llm"
        comp4.output_targets = ["memory", "console"]
        # Remove auto-created attributes to test output_targets fallback
        del comp4.to
        del comp4._output
        components["llm"] = comp4

        # Component with object target
        comp5 = Mock()
        comp5.name = "tool"
        target_obj = Mock()
        target_obj.name = "response_handler"
        comp5.to = target_obj
        components["tool"] = comp5

        # Component with no routing
        comp6 = Mock()
        comp6.name = "standalone"
        # Remove all routing attributes
        del comp6.to
        del comp6._output
        del comp6.output_targets
        components["standalone"] = comp6

        return components

    def test_routing_target_extraction_string(self, router):
        """Test extracting routing targets from string."""
        component = Mock()
        component.name = "test"
        component.to = "target_component"

        targets = router._extract_routing_targets(component)
        assert targets == ["target_component"]

    def test_routing_target_extraction_list(self, router):
        """Test extracting routing targets from list."""
        component = Mock()
        component.name = "test"
        component.to = ["target1", "target2", "target3"]

        targets = router._extract_routing_targets(component)
        assert targets == ["target1", "target2", "target3"]

    def test_routing_target_extraction_object_with_name(self, router):
        """Test extracting routing targets from object with name attribute."""
        component = Mock()
        component.name = "test"
        target_obj = Mock()
        target_obj.name = "target_component"
        component.to = target_obj

        targets = router._extract_routing_targets(component)
        assert targets == ["target_component"]

    def test_routing_target_extraction_output_property(self, router):
        """Test extracting targets from _output property."""
        component = Mock()
        component.name = "test"
        component._output = "output_target"
        # Remove 'to' property to test _output fallback
        del component.to

        targets = router._extract_routing_targets(component)
        assert targets == ["output_target"]

    def test_routing_target_extraction_output_targets_property(self, router):
        """Test extracting targets from output_targets property."""
        component = Mock()
        component.name = "test"
        component.output_targets = ["target1", "target2"]
        # Remove 'to' and '_output' properties to test output_targets fallback
        del component.to
        del component._output

        targets = router._extract_routing_targets(component)
        assert targets == ["target1", "target2"]

    def test_routing_target_extraction_priority(self, router):
        """Test that 'to' property takes priority over other properties."""
        component = Mock()
        component.name = "test"
        component.to = "primary_target"
        component._output = "secondary_target"
        component.output_targets = ["tertiary_target"]

        targets = router._extract_routing_targets(component)
        assert targets == ["primary_target"]

    def test_routing_target_extraction_none(self, router):
        """Test extracting targets when no routing is configured."""
        component = Mock()
        component.name = "test"
        # Remove all routing properties
        del component.to
        del component._output
        del component.output_targets

        targets = router._extract_routing_targets(component)
        assert targets == []

    def test_routing_table_configuration(self, router, mock_components):
        """Test complete routing table configuration."""
        # Register all components
        for component in mock_components.values():
            router.register_component(component)

        # Configure routing
        router.configure_routing()

        # Verify routing table
        expected_routes = {
            "input": ["agent"],
            "agent": ["tool1", "tool2", "output"],
            "api_input": ["coding_agent"],
            "llm": ["memory", "console"],
            "tool": ["response_handler"],
            "standalone": []
        }

        for component_name, expected_targets in expected_routes.items():
            actual_targets = router._routing_table.get(component_name, [])
            assert actual_targets == expected_targets, f"Failed for {component_name}: expected {expected_targets}, got {actual_targets}"

    def test_routing_inference_for_undefined_components(self, router):
        """Test routing with components that have no explicit routing."""
        # Create components without explicit routing
        input_comp = Mock()
        input_comp.name = "api_input"
        input_comp.__class__.__name__ = "api_input"
        # Remove all routing attributes
        del input_comp.to
        del input_comp._output
        del input_comp.output_targets

        agent_comp = Mock()
        agent_comp.name = "coding_agent"
        agent_comp.__class__.__name__ = "llm"
        # Remove all routing attributes
        del agent_comp.to
        del agent_comp._output
        del agent_comp.output_targets

        output_comp = Mock()
        output_comp.name = "console_output"
        output_comp.__class__.__name__ = "console_output"
        # Remove all routing attributes
        del output_comp.to
        del output_comp._output
        del output_comp.output_targets

        # Register components
        router.register_component(input_comp)
        router.register_component(agent_comp)
        router.register_component(output_comp)

        # Configure routing
        router.configure_routing()

        # Verify routing inference worked
        input_targets = router._routing_table.get("api_input", [])
        agent_targets = router._routing_table.get("coding_agent", [])
        output_targets = router._routing_table.get("console_output", [])

        # System should infer routing patterns based on component names
        assert "coding_agent" in input_targets  # api_input -> coding_agent
        assert "console_output" in agent_targets  # coding_agent -> console_output
        assert output_targets == []  # console_output has no targets

    async def test_component_to_component_message_delivery(self, router):
        """Test message delivery between components."""
        # Create mock components
        source_comp = Mock()
        source_comp.name = "source"
        source_comp._received_responses = {}

        target_comp = Mock()
        target_comp.name = "target"
        target_comp.input = Mock(return_value="response_data")

        # Register components
        router.register_component(source_comp)
        router.register_component(target_comp)

        # Test send_to_component_with_response
        success, request_id = await router.send_to_component_with_response(
            name="target",
            source_component_name="source",
            data={"action": "test", "inputs": {"key": "value"}}
        )

        # Verify success
        assert success
        assert request_id is not None

        # Verify target component was called with tool format (action, inputs)
        target_comp.input.assert_called_once_with("test", {"key": "value"})

        # Verify response was stored in source component
        assert request_id in source_comp._received_responses
        response = source_comp._received_responses[request_id]
        assert response["result"] == "response_data"
        assert response["source_component"] == "target"

    async def test_component_routing_via_emit_from_component(self, router):
        """Test automatic routing when emitting from component."""
        # Create components with routing
        source_comp = Mock()
        source_comp.name = "source"
        source_comp.to = "target"

        target_comp = Mock()
        target_comp.name = "target"
        target_comp.input = AsyncMock(return_value="processed")

        # Register and configure
        router.register_component(source_comp)
        router.register_component(target_comp)
        router.configure_routing()

        # Emit from source component
        await router.emit_from_component("source", "test.event", {"data": "test"})

        # Verify target was called
        target_comp.input.assert_called_once()

    def test_get_routing_info(self, router, mock_components):
        """Test getting routing information for components."""
        # Register components and configure routing
        for component in mock_components.values():
            router.register_component(component)
        router.configure_routing()

        # Test routing info for component with targets
        info = router.get_routing_info("agent")
        assert info["component_name"] == "agent"
        assert info["targets"] == ["tool1", "tool2", "output"]
        assert info["is_registered"] == True
        assert info["target_count"] == 3

        # Test routing info for component without targets
        info = router.get_routing_info("standalone")
        assert info["component_name"] == "standalone"
        assert info["targets"] == []
        assert info["is_registered"] == True
        assert info["target_count"] == 0

        # Test routing info for non-existent component
        info = router.get_routing_info("nonexistent")
        assert info["component_name"] == "nonexistent"
        assert info["targets"] == []
        assert info["is_registered"] == False
        assert info["target_count"] == 0

    async def test_routing_with_async_components(self, router):
        """Test routing with async component input methods."""
        # Create async component
        async_comp = Mock()
        async_comp.name = "async_target"
        async_comp.input = AsyncMock(return_value="async_result")

        router.register_component(async_comp)

        # Test async delivery
        success, request_id = await router.send_to_component_with_response(
            name="async_target",
            source_component_name="test_source",
            data={"test": "data"}
        )

        assert success
        async_comp.input.assert_called_once_with({"test": "data"})

    async def test_routing_error_handling(self, router):
        """Test routing error handling for missing components."""
        # Try to route to non-existent component
        success, request_id = await router.send_to_component_with_response(
            name="nonexistent",
            source_component_name="test_source",
            data={"test": "data"}
        )

        assert not success
        assert request_id is not None  # Should still generate request ID

    def test_message_bus_compatibility_methods(self, router):
        """Test MessageBusIntegration compatibility methods."""
        # Test message_bus property
        assert router.message_bus == router

        # Test register_component_handler (should not raise)
        router.register_component_handler("test_component", lambda x: x)

    async def test_tool_action_format_handling(self, router):
        """Test that router handles tool action format correctly."""
        # Create tool component that expects input(action, inputs)
        tool_comp = Mock()
        tool_comp.name = "planning_tools"

        def tool_input(action, inputs=None):
            return f"Tool executed: {action} with {inputs}"

        tool_comp.input = tool_input

        router.register_component(tool_comp)

        # Test sending tool request
        success, request_id = await router.send_to_component_with_response(
            name="planning_tools",
            source_component_name="test_agent",
            data={"action": "write_todos", "inputs": {"todos": ["task1", "task2"]}}
        )

        assert success
        # Should have called with correct format

    def test_routing_table_statistics(self, router, mock_components):
        """Test routing statistics and metrics."""
        # Register components and configure
        for component in mock_components.values():
            router.register_component(component)
        router.configure_routing()

        # Get statistics
        stats = router.get_stats()

        assert stats["components_count"] == len(mock_components)
        assert "routing_table_size" in stats

    async def test_concurrent_routing_operations(self, router):
        """Test concurrent routing operations don't interfere."""
        # Create multiple target components
        targets = []
        for i in range(5):
            comp = Mock()
            comp.name = f"target_{i}"
            comp.input = AsyncMock(return_value=f"result_{i}")
            targets.append(comp)
            router.register_component(comp)

        # Send concurrent requests
        tasks = []
        for i, target in enumerate(targets):
            task = router.send_to_component_with_response(
                name=f"target_{i}",
                source_component_name="test_source",
                data={"test": f"data_{i}"}
            )
            tasks.append(task)

        # Wait for all
        results = await asyncio.gather(*tasks)

        # Verify all succeeded
        for success, request_id in results:
            assert success
            assert request_id is not None

        # Verify all targets were called
        for target in targets:
            target.input.assert_called_once()

    def test_routing_with_edge_case_names(self, router):
        """Test routing with edge case component names."""
        # Create components with special names
        special_comps = []

        # Component with underscore
        comp1 = Mock()
        comp1.name = "api_input_v2"
        comp1.to = "coding_agent_v3"
        special_comps.append(comp1)

        # Component with numbers
        comp2 = Mock()
        comp2.name = "agent123"
        comp2.to = "tool456"
        special_comps.append(comp2)

        # Component with hyphens (if supported)
        comp3 = Mock()
        comp3.name = "test-component"
        comp3.to = "target-component"
        special_comps.append(comp3)

        # Register and configure
        for comp in special_comps:
            router.register_component(comp)
        router.configure_routing()

        # Verify routing works with special names
        assert "coding_agent_v3" in router._routing_table["api_input_v2"]
        assert "tool456" in router._routing_table["agent123"]
        assert "target-component" in router._routing_table["test-component"]