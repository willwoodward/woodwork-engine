"""Unit tests for Internal Features Integration."""

import pytest

from woodwork.components.internal_features import InternalFeatureRegistry, WorkflowsFeature


@pytest.mark.unit
@pytest.mark.internal_features
@pytest.mark.workflows
@pytest.mark.slow
class TestWorkflowsFeatureIntegration:
    """Integration tests for WorkflowsFeature with actual registration."""

    def setup_method(self):
        """Ensure workflows feature is registered before each test."""
        from woodwork.components.internal_features.base import InternalFeatureRegistry

        InternalFeatureRegistry.register("workflows", WorkflowsFeature)

    def test_workflows_feature_is_registered(self):
        """Test that WorkflowsFeature is properly registered."""
        registered_features = InternalFeatureRegistry.get_registered_features()
        assert "workflows" in registered_features
        assert registered_features["workflows"] is WorkflowsFeature

    def test_workflows_feature_creation(self):
        """Test that workflows feature is created when enabled."""
        config = {"workflows": True}
        features = InternalFeatureRegistry.create_features(config)

        # Should have one feature
        assert len(features) == 1
        assert isinstance(features[0], WorkflowsFeature)

    def test_no_features_created_when_disabled(self):
        """Test that no features are created when none are enabled."""
        config = {"workflows": False, "other_setting": True}
        features = InternalFeatureRegistry.create_features(config)

        # Should have no features because workflows is False
        assert len([f for f in features if isinstance(f, WorkflowsFeature)]) == 0
