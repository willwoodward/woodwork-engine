"""Tests for DeclarativeRouter component."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from woodwork.core.message_bus.declarative_router import DeclarativeRouter
from tests.unit.fixtures.mock_components import MockMessageBus, create_test_components, create_test_component_configs, create_workflow_inference_configs


class TestDeclarativeRouter:
    """Test suite for DeclarativeRouter."""

    @pytest.fixture
    def mock_message_bus(self):
        return MockMessageBus()

    @pytest.fixture
    def test_components(self):
        return create_test_components()

    @pytest.fixture
    def test_component_configs(self):
        return create_test_component_configs()

    @pytest.fixture
    def router(self, mock_message_bus):
        return DeclarativeRouter(mock_message_bus)

    def test_initialization(self, router, mock_message_bus):
        """Test router initializes correctly."""
        assert router.message_bus == mock_message_bus
        assert router.routing_table == {}
        assert router.component_configs == {}
        assert router.stats["messages_routed"] == 0

    def test_configure_from_components(self, router, test_component_configs):
        """Test component configuration."""
        router.configure_from_components(test_component_configs)

        assert len(router.component_configs) == len(test_component_configs)
        assert "test_agent" in router.component_configs
        assert "test_tool" in router.component_configs

    def test_extract_targets_string(self, router):
        """Test extracting routing targets from string."""
        targets = router._extract_targets("test_component")
        assert targets == ["test_component"]

    def test_extract_targets_list(self, router):
        """Test extracting routing targets from list."""
        targets = router._extract_targets(["comp1", "comp2"])
        assert targets == ["comp1", "comp2"]

    def test_extract_targets_component_object(self, router):
        """Test extracting targets from component object."""
        mock_comp = Mock()
        mock_comp.name = "test_comp"
        targets = router._extract_targets(mock_comp)
        assert targets == ["test_comp"]

    def test_extract_targets_none(self, router):
        """Test extracting targets when none provided."""
        targets = router._extract_targets(None)
        assert targets == []

    async def test_send_to_component(self, router, mock_message_bus):
        """Test sending message to component."""
        data = {"action": "test", "inputs": {}}
        success = await router.send_to_component("target", "source", data)

        assert success
        assert len(mock_message_bus.sent_messages) == 1

        message = mock_message_bus.sent_messages[0]
        assert message.target_component == "target"
        assert message.sender_component == "source"
        assert message.payload["data"] == data

    async def test_send_to_component_with_response(self, router, mock_message_bus):
        """Test sending message with response requirement."""
        data = {"action": "test", "inputs": {}}
        success, request_id = await router.send_to_component_with_response(
            "target", "source", data
        )

        assert success
        assert request_id.startswith("source_target_")
        assert len(mock_message_bus.sent_messages) == 1

        message = mock_message_bus.sent_messages[0]
        assert message.payload["_response_required"] is True
        assert message.payload["_request_id"] == request_id
        assert message.payload["_response_target"] == "source"

    async def test_setup_component_response_wrapper(self, router, test_component_configs, test_components):
        """Test setting up component response wrapper."""
        # Add the actual component object to the config
        test_component_configs["test_tool"]["object"] = test_components["test_tool"]
        router.component_configs = test_component_configs

        await router._setup_component_response_wrapper(
            "test_tool", "req_123", "test_agent"
        )

        # Should register handler with message bus
        assert "test_tool" in router.message_bus.component_handlers

    async def test_route_component_output_no_targets(self, router):
        """Test routing when component has no targets."""
        success = await router.route_component_output(
            "source", "test_event", {"data": "test"}, "session_123"
        )
        assert success  # No targets is not a failure

    async def test_route_component_output_with_targets(self, router, mock_message_bus):
        """Test routing with configured targets."""
        router.routing_table = {"source": ["target1", "target2"]}

        success = await router.route_component_output(
            "source", "test_event", {"data": "test"}, "session_123"
        )

        assert success
        assert len(mock_message_bus.sent_messages) == 2
        assert router.stats["messages_routed"] == 2

    async def test_broadcast_hook_event(self, router, mock_message_bus):
        """Test broadcasting hook events."""
        success = await router.broadcast_hook_event(
            "source", "agent.thought", {"thought": "test"}, "session_123"
        )

        assert success
        assert len(mock_message_bus.published_messages) == 1

    def test_add_routing_target(self, router):
        """Test dynamically adding routing target."""
        router.add_routing_target("comp1", "comp2")

        assert "comp1" in router.routing_table
        assert "comp2" in router.routing_table["comp1"]
        assert router.stats["active_routes"] == 1

    def test_remove_routing_target(self, router):
        """Test removing routing target."""
        router.routing_table = {"comp1": ["comp2", "comp3"]}
        router.stats["active_routes"] = 2

        success = router.remove_routing_target("comp1", "comp2")

        assert success
        assert "comp2" not in router.routing_table["comp1"]
        assert router.stats["active_routes"] == 1

    def test_get_routing_targets(self, router):
        """Test getting routing targets for component."""
        router.routing_table = {"comp1": ["comp2", "comp3"]}

        targets = router.get_routing_targets("comp1")
        assert targets == ["comp2", "comp3"]

        # Should return copy, not reference
        targets.append("comp4")
        assert "comp4" not in router.routing_table["comp1"]

    def test_validate_routing_configuration(self, router, test_components):
        """Test routing configuration validation."""
        router.component_configs = test_components
        router.routing_table = {
            "test_agent": ["test_tool"],
            "test_tool": ["nonexistent_component"]
        }

        validation = router.validate_routing_configuration()

        assert not validation["valid"]
        assert "nonexistent_component" in str(validation["issues"])

    def test_workflow_inference(self, router):
        """Test automatic workflow inference."""
        components = create_workflow_inference_configs()

        router.component_configs = components
        router._infer_workflow_chains()

        # Should infer input -> agent routing
        assert "input" in router.routing_table
        assert "agent" in router.routing_table["input"]

        # Should infer agent -> output routing
        assert "agent" in router.routing_table
        assert "output" in router.routing_table["agent"] or "_console_output" in router.routing_table["agent"]


class TestDeclarativeRouterErrorHandling:
    """Test error handling in DeclarativeRouter."""

    @pytest.fixture
    def router(self):
        mock_bus = Mock()
        mock_bus.send_to_component = AsyncMock(return_value=False)
        return DeclarativeRouter(mock_bus)

    async def test_send_to_component_failure(self, router):
        """Test handling of send failures."""
        success = await router.send_to_component("target", "source", {})
        assert not success

    async def test_route_component_output_partial_failure(self, router):
        """Test routing with some target failures."""
        router.routing_table = {"source": ["target1", "target2"]}

        # Mock bus to fail on second message
        call_count = 0

        async def mock_send(envelope):
            nonlocal call_count
            call_count += 1
            return call_count == 1  # First succeeds, second fails

        router.message_bus.send_to_component = mock_send

        success = await router.route_component_output(
            "source", "test_event", {}, "session"
        )

        assert not success  # Overall failure due to partial failure
        assert router.stats["messages_routed"] == 1
        assert router.stats["routing_failures"] == 1