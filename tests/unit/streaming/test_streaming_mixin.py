"""Tests for StreamingMixin component."""

import pytest
from unittest.mock import Mock, AsyncMock
from woodwork.components.streaming_mixin import StreamingMixin


class MockStreamingComponent(StreamingMixin):
    """Mock component that uses StreamingMixin."""

    def __init__(self, name="test_component", config=None, **kwargs):
        self.name = name
        self.config = config or {}
        super().__init__(**kwargs)


class TestStreamingMixin:
    """Test suite for StreamingMixin."""

    def test_initialization_without_streaming(self):
        """Test component without streaming enabled."""
        component = MockStreamingComponent()

        assert not component.streaming_enabled
        assert not component.streaming_input
        assert not component.streaming_output
        assert component.component_name == "test_component"

    def test_initialization_with_streaming_enabled(self):
        """Test component with streaming enabled."""
        config = {"streaming": True}
        component = MockStreamingComponent(config=config)

        assert component.streaming_enabled
        assert component.streaming_input  # Default is True
        assert component.streaming_output  # Default is True

    def test_custom_component_name(self):
        """Test custom component name."""
        component = MockStreamingComponent(name="custom_name")
        assert component.component_name == "custom_name"

    def test_streaming_capabilities_override(self):
        """Test overriding streaming capabilities."""

        class CustomComponent(StreamingMixin):
            def __init__(self, **kwargs):
                self.name = "custom"
                self.config = kwargs.get('config', {})
                super().__init__(**kwargs)

            def _can_stream_input(self):
                return False  # Override to disable input streaming

            def _can_stream_output(self):
                return True  # Keep output streaming

        config = {"streaming": True}
        component = CustomComponent(config=config)

        assert component.streaming_enabled
        assert not component.streaming_input  # Overridden to False
        assert component.streaming_output  # Remains True

    def test_stream_manager_property(self):
        """Test stream manager property."""
        component = MockStreamingComponent()

        # Initially None
        assert component._stream_manager is None

        # Can be set
        mock_manager = Mock()
        component._stream_manager = mock_manager
        assert component._stream_manager == mock_manager

    def test_configuration_parsing(self):
        """Test various configuration formats."""
        # Boolean streaming config
        config1 = {"streaming": True}
        component1 = MockStreamingComponent(config=config1)
        assert component1.streaming_enabled

        # Disabled streaming
        config2 = {"streaming": False}
        component2 = MockStreamingComponent(config=config2)
        assert not component2.streaming_enabled

        # No streaming config (default False)
        config3 = {}
        component3 = MockStreamingComponent(config=config3)
        assert not component3.streaming_enabled

    def test_mixin_inheritance_compatibility(self):
        """Test that mixin works with other base classes."""

        class BaseComponent:
            def __init__(self, base_value=42, **kwargs):
                self.base_value = base_value

        class MixedComponent(StreamingMixin, BaseComponent):
            def __init__(self, **kwargs):
                self.name = "mixed"
                self.config = kwargs.get('config', {})
                super().__init__(**kwargs)

        # Should work with multiple inheritance
        component = MixedComponent(base_value=99, config={"streaming": True})
        assert component.base_value == 99
        assert component.streaming_enabled

    def test_default_streaming_methods(self):
        """Test default streaming capability methods."""
        component = MockStreamingComponent()

        # Default implementations
        assert component._can_stream_input() is True
        assert component._can_stream_output() is True


class TestStreamingMixinIntegration:
    """Test integration scenarios for StreamingMixin."""

    def test_component_with_no_config(self):
        """Test component without any config attribute."""

        class MinimalComponent(StreamingMixin):
            def __init__(self):
                # No config attribute set
                super().__init__()

        component = MinimalComponent()
        assert not component.streaming_enabled
        assert component.component_name == "unknown"

    def test_component_with_kwargs_config(self):
        """Test component configured via kwargs."""

        class KwargsComponent(StreamingMixin):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)

        component = KwargsComponent(
            config={"streaming": True},
            name="kwargs_test"
        )
        assert component.streaming_enabled
        assert component.component_name == "kwargs_test"