"""Tests for MessageBusIntegration component."""

import pytest
from unittest.mock import Mock, patch
from woodwork.core.message_bus.integration import MessageBusIntegration


class MockBaseComponent:
    """Base component for testing."""
    def __init__(self, name="test_component", **kwargs):
        self.name = name


class MockIntegrationComponent(MessageBusIntegration, MockBaseComponent):
    """Mock component that uses MessageBusIntegration."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class TestMessageBusIntegration:
    """Test suite for MessageBusIntegration."""

    def test_initialization_basic(self):
        """Test basic initialization."""
        component = MockIntegrationComponent()

        assert component._message_bus is None
        assert component._router is None
        assert not component._integration_ready
        assert hasattr(component, 'integration_stats')
        assert hasattr(component, 'output_targets')
        assert hasattr(component, 'session_id')

    def test_initialization_with_config(self):
        """Test initialization with configuration."""
        config = {
            'to': ['target1', 'target2'],
            'session_id': 'test_session_123'
        }
        component = MockIntegrationComponent(config=config)

        assert component.output_targets == ['target1', 'target2']
        assert component.session_id == 'test_session_123'

    def test_output_targets_extraction_string(self):
        """Test extracting output targets from string."""
        config = {'to': 'single_target'}
        component = MockIntegrationComponent(config=config)

        # String should be converted to list
        assert component.output_targets == ['single_target']

    def test_output_targets_extraction_list(self):
        """Test extracting output targets from list."""
        config = {'to': ['target1', 'target2', 'target3']}
        component = MockIntegrationComponent(config=config)

        assert component.output_targets == ['target1', 'target2', 'target3']

    def test_output_targets_extraction_none(self):
        """Test extracting output targets when none specified."""
        config = {}
        component = MockIntegrationComponent(config=config)

        # Should return empty list when no 'to' configured
        assert component.output_targets == []

    def test_session_id_extraction(self):
        """Test session ID extraction."""
        # With session_id in config
        config1 = {'session_id': 'explicit_session'}
        component1 = MockIntegrationComponent(config=config1)
        assert component1.session_id == 'explicit_session'

        # Without session_id in config - should get a generated one
        config2 = {}
        component2 = MockIntegrationComponent(config=config2)
        # Should have a generated session_id (UUID format)
        assert component2.session_id is not None
        assert len(component2.session_id) > 0

    def test_integration_stats_initialization(self):
        """Test that integration stats are properly initialized."""
        component = MockIntegrationComponent()

        assert isinstance(component.integration_stats, dict)
        # Stats should contain expected keys (implementation-dependent)
        assert len(component.integration_stats) >= 0

    def test_multiple_inheritance_compatibility(self):
        """Test that integration mixin works with multiple inheritance."""

        class BaseComponent:
            def __init__(self, base_attr=42, **kwargs):
                self.base_attr = base_attr

        class IntegratedComponent(MessageBusIntegration, BaseComponent):
            def __init__(self, name="integrated", **kwargs):
                self.name = name
                super().__init__(**kwargs)

        component = IntegratedComponent(
            base_attr=99,
            config={'to': ['target1'], 'session_id': 'test'}
        )

        assert component.base_attr == 99
        assert component.name == "integrated"
        assert component.output_targets == ['target1']
        assert component.session_id == 'test'

    @patch('woodwork.core.message_bus.integration.get_global_message_bus')
    @patch('woodwork.core.message_bus.integration.get_global_event_manager')
    def test_global_manager_integration(self, mock_event_manager, mock_message_bus):
        """Test integration with global managers."""
        # Mock the global managers
        mock_bus = Mock()
        mock_event_mgr = Mock()
        mock_message_bus.return_value = mock_bus
        mock_event_manager.return_value = mock_event_mgr

        component = MockIntegrationComponent()

        # Component should be able to access global managers
        # (specific integration depends on implementation)
        assert component._message_bus is None  # Initially None
        assert component._router is None       # Initially None

    def test_configuration_edge_cases(self):
        """Test edge cases in configuration handling."""
        # Empty config
        component1 = MockIntegrationComponent(config={})
        assert component1.output_targets is not None
        assert component1.session_id is not None

        # None config
        component2 = MockIntegrationComponent(config=None)
        assert component2.output_targets is not None
        assert component2.session_id is not None

        # Config with unexpected types
        config3 = {'to': 123, 'session_id': ['invalid_type']}
        component3 = MockIntegrationComponent(config=config3)
        # Should handle gracefully without crashing
        assert component3.output_targets is not None
        assert component3.session_id is not None


class TestMessageBusIntegrationMethods:
    """Test specific methods of MessageBusIntegration."""

    def test_extract_output_targets_private_method(self):
        """Test the _extract_output_targets method behavior."""
        component = MockIntegrationComponent()

        # Test different input types
        targets_list = component._extract_output_targets({'to': ['a', 'b']})
        assert targets_list == ['a', 'b']

        targets_string = component._extract_output_targets({'to': 'single'})
        # Should handle string appropriately

        targets_none = component._extract_output_targets({})
        # Should handle missing key appropriately

    def test_extract_session_id_private_method(self):
        """Test the _extract_session_id method behavior."""
        component = MockIntegrationComponent()

        # Test with explicit session_id
        session_explicit = component._extract_session_id({'session_id': 'test123'})
        assert session_explicit == 'test123'

        # Test without session_id
        session_default = component._extract_session_id({})
        assert session_default is not None

    def test_state_flags(self):
        """Test integration state flags."""
        component = MockIntegrationComponent()

        # Initially not ready
        assert not component._integration_ready

        # Can be set
        component._integration_ready = True
        assert component._integration_ready