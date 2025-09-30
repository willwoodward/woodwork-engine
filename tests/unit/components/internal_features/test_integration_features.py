"""Unit tests for Internal Features Integration."""

import pytest
from unittest.mock import Mock, patch
from woodwork.components.internal_features import InternalFeatureRegistry


@pytest.mark.unit
@pytest.mark.internal_features
@pytest.mark.graph_cache
class TestGraphCacheFeatureIntegration:
    """Integration tests for GraphCacheFeature with actual registration."""

    def setup_method(self):
        """Ensure graph cache feature is registered before each test."""
        from woodwork.components.internal_features.graph_cache import GraphCacheFeature
        from woodwork.components.internal_features.base import InternalFeatureRegistry
        InternalFeatureRegistry.register("graph_cache", GraphCacheFeature)

    def test_graph_cache_feature_is_registered(self):
        """Test that GraphCacheFeature is properly registered."""
        # Import should trigger registration
        from woodwork.components.internal_features.graph_cache import GraphCacheFeature

        registered_features = InternalFeatureRegistry.get_registered_features()
        assert "graph_cache" in registered_features
        assert registered_features["graph_cache"] is GraphCacheFeature

    def test_graph_cache_feature_creation(self):
        """Test that graph_cache feature is created when enabled."""
        from woodwork.components.internal_features.graph_cache import GraphCacheFeature

        config = {"graph_cache": True}
        features = InternalFeatureRegistry.create_features(config)

        # Should have one feature
        assert len(features) == 1
        assert isinstance(features[0], GraphCacheFeature)

    def test_no_features_created_when_disabled(self):
        """Test that no features are created when none are enabled."""
        config = {"graph_cache": False, "other_setting": True}
        features = InternalFeatureRegistry.create_features(config)

        # Should have no features because graph_cache is False
        assert len([f for f in features if isinstance(f, type(GraphCacheFeature))]) == 0