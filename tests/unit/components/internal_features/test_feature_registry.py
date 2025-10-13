"""Unit tests for InternalFeatureRegistry."""

import pytest
from unittest.mock import Mock, patch
from woodwork.components.internal_features import InternalFeatureRegistry


@pytest.mark.unit
@pytest.mark.internal_features
class TestInternalFeatureRegistry:
    def test_register_feature(self):
        """Test feature registration."""
        # Clear registry for clean test
        InternalFeatureRegistry._features.clear()

        test_feature_class = Mock()
        test_feature_class.__name__ = "MockFeature"
        InternalFeatureRegistry.register("test_feature", test_feature_class)

        assert InternalFeatureRegistry._features["test_feature"] is test_feature_class

    def test_create_features_with_enabled_flag(self):
        """Test feature creation with enabled flag."""
        # Clear registry and register test feature
        InternalFeatureRegistry._features.clear()
        test_feature_class = Mock()
        test_feature_class.__name__ = "MockFeature"
        InternalFeatureRegistry.register("test_feature", test_feature_class)

        config = {"test_feature": True, "other_flag": False}
        features = InternalFeatureRegistry.create_features(config)

        test_feature_class.assert_called_once()
        assert len(features) == 1

    def test_create_features_with_disabled_flag(self):
        """Test that disabled features are not created."""
        # Clear registry and register test feature
        InternalFeatureRegistry._features.clear()
        test_feature_class = Mock()
        test_feature_class.__name__ = "MockFeature"
        InternalFeatureRegistry.register("test_feature", test_feature_class)

        config = {"test_feature": False}
        features = InternalFeatureRegistry.create_features(config)

        test_feature_class.assert_not_called()
        assert len(features) == 0

    def test_create_features_without_flag(self):
        """Test that features without config flags are not created."""
        # Clear registry and register test feature
        InternalFeatureRegistry._features.clear()
        test_feature_class = Mock()
        test_feature_class.__name__ = "MockFeature"
        InternalFeatureRegistry.register("test_feature", test_feature_class)

        config = {}
        features = InternalFeatureRegistry.create_features(config)

        test_feature_class.assert_not_called()
        assert len(features) == 0

    def test_get_registered_features(self):
        """Test getting registered features."""
        # Clear registry and register test feature
        InternalFeatureRegistry._features.clear()
        test_feature_class = Mock()
        test_feature_class.__name__ = "MockFeature"
        InternalFeatureRegistry.register("test_feature", test_feature_class)

        features = InternalFeatureRegistry.get_registered_features()
        assert features["test_feature"] is test_feature_class

    @patch('woodwork.components.internal_features.graph_cache.GraphCacheFeature')
    def test_ensure_features_loaded(self, mock_graph_cache):
        """Test that _ensure_features_loaded imports available features."""
        # Clear registry
        InternalFeatureRegistry._features.clear()

        # Call _ensure_features_loaded directly
        InternalFeatureRegistry._ensure_features_loaded()

        # Verify import was attempted (even if mocked)
        # The actual registration happens in the module when imported