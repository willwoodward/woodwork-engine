"""Integration tests for Internal Features with Component System."""

import pytest
from unittest.mock import Mock, patch
from woodwork.components.internal_features import InternalFeatureRegistry, InternalComponentManager


class MockComponent:
    """Mock component class for testing internal features."""

    def __init__(self, **config):
        self.name = config.get("name", "test_component")
        self.component = config.get("component", "test")
        self.type = config.get("type", "test")
        self.config = config

        # Create internal component manager
        task_master = config.get('task_m', None)
        self._internal_component_manager = InternalComponentManager(task_master)

        # Setup internal features
        self._internal_features = InternalFeatureRegistry.create_features(config)
        self._setup_internal_features(config)

    def _setup_internal_features(self, config):
        """Setup internal features, create required components, and register hooks/pipes."""
        for feature in self._internal_features:
            try:
                # Create required components for this feature
                self._create_required_components(feature)

                # Setup the feature with component manager access
                feature.setup(self, config, self._internal_component_manager)

            except Exception as e:
                # Handle gracefully for test
                print(f"Feature setup failed: {e}")

    def _create_required_components(self, feature):
        """Create all components required by a feature."""
        required_components = feature.get_required_components()

        for component_spec in required_components:
            component_id = component_spec["component_id"]
            component_type = component_spec["component_type"]
            component_config = component_spec["config"]
            is_optional = component_spec.get("optional", False)

            try:
                self._internal_component_manager.get_or_create_component(
                    component_id, component_type, component_config
                )
            except Exception as e:
                if not is_optional:
                    raise RuntimeError(f"Failed to create required internal component {component_id}: {e}")

    def get_internal_component(self, component_id: str):
        """Get an internal component by ID."""
        return self._internal_component_manager.get_component(component_id)

    def close(self):
        """Clean up internal features and components."""
        try:
            # Teardown features first
            for feature in self._internal_features:
                try:
                    feature.teardown(self, self._internal_component_manager)
                except Exception as e:
                    pass

            # Then cleanup all internal components
            self._internal_component_manager.cleanup_components()
        except Exception as e:
            pass


@pytest.mark.integration
@pytest.mark.internal_features
@pytest.mark.graph_cache
class TestComponentInternalFeaturesIntegration:

    def setup_method(self):
        """Ensure graph cache feature is registered before each test."""
        from woodwork.components.internal_features.graph_cache import GraphCacheFeature
        from woodwork.components.internal_features.base import InternalFeatureRegistry
        InternalFeatureRegistry.register("graph_cache", GraphCacheFeature)

    @patch('woodwork.components.knowledge_bases.graph_databases.neo4j.neo4j')
    def test_component_with_graph_cache_feature(self, mock_neo4j_factory):
        """Test component initialization with graph_cache feature enabled."""
        # Setup mocks
        mock_neo4j_instance = Mock()
        mock_neo4j_factory.return_value = mock_neo4j_instance

        # Create component with graph_cache enabled
        config = {
            "name": "test_component",
            "graph_cache": True,
        }

        comp = MockComponent(**config)

        # Mock the model for API key
        mock_model = Mock()
        mock_model._api_key = "test-api-key"
        comp.model = mock_model

        # Setup the feature manually to test full integration
        if comp._internal_features:
            feature = comp._internal_features[0]
            feature.setup(comp, config, comp._internal_component_manager)

            # Verify Neo4j component was created (called at least once with correct config)
            assert mock_neo4j_factory.call_count >= 1
            # Check the call that includes the API key
            api_key_call = None
            for call in mock_neo4j_factory.call_args_list:
                if 'api_key' in call[1]:
                    api_key_call = call
                    break

            assert api_key_call is not None
            call_kwargs = api_key_call[1]
            assert "test-api-key" in call_kwargs["api_key"]
            assert "test_component_cache" in call_kwargs["name"]

            # Verify component has cache references
            assert hasattr(comp, '_graph_cache')
            assert comp._cache_mode is True
            assert comp._graph_cache is mock_neo4j_instance

        # Verify internal component manager was set up
        assert hasattr(comp, '_internal_component_manager')
        assert hasattr(comp, '_internal_features')
        assert len(comp._internal_features) == 1

    def test_component_without_internal_features(self):
        """Test component initialization without internal features."""
        config = {
            "name": "test_component",
            "graph_cache": False,
        }

        comp = MockComponent(**config)

        # Verify internal systems are still set up but empty
        assert hasattr(comp, '_internal_component_manager')
        assert hasattr(comp, '_internal_features')
        assert len(comp._internal_features) == 0

    @patch('woodwork.components.knowledge_bases.graph_databases.neo4j.neo4j')
    def test_component_cleanup(self, mock_neo4j_factory):
        """Test that component cleanup properly tears down internal features."""
        mock_neo4j_instance = Mock()
        mock_neo4j_factory.return_value = mock_neo4j_instance

        config = {
            "name": "test_component",
            "graph_cache": True,
        }

        comp = MockComponent(**config)

        # Mock the model for API key
        mock_model = Mock()
        mock_model._api_key = "test-api-key"
        comp.model = mock_model

        # Setup feature
        if comp._internal_features:
            feature = comp._internal_features[0]
            feature.setup(comp, config, comp._internal_component_manager)

        # Close the component
        comp.close()

        # Verify Neo4j component was closed (may be called multiple times for multiple components)
        assert mock_neo4j_instance.close.call_count >= 1

    @patch('woodwork.components.knowledge_bases.graph_databases.neo4j.neo4j')
    def test_component_get_internal_component(self, mock_neo4j_factory):
        """Test that component can access internal components."""
        mock_neo4j_instance = Mock()
        mock_neo4j_factory.return_value = mock_neo4j_instance

        config = {
            "name": "test_component",
            "graph_cache": True,
        }

        comp = MockComponent(**config)

        # Mock the model for API key
        mock_model = Mock()
        mock_model._api_key = "test-api-key"
        comp.model = mock_model

        # Setup feature
        if comp._internal_features:
            feature = comp._internal_features[0]
            feature.setup(comp, config, comp._internal_component_manager)

            # Component should be able to access internal Neo4j component
            neo4j_component = comp.get_internal_component("test_component_graph_cache_neo4j")
            assert neo4j_component is mock_neo4j_instance

    def test_component_handles_missing_api_key(self):
        """Test that component handles missing API key gracefully."""
        config = {
            "name": "test_component",
            "graph_cache": True,
        }

        comp = MockComponent(**config)
        # No model with API key, so feature setup should fail but component should still exist
        assert comp.name == "test_component"
        assert hasattr(comp, '_internal_component_manager')

    def test_multiple_components_have_separate_managers(self):
        """Test that multiple components have separate internal component managers."""
        config1 = {
            "name": "component1",
            "graph_cache": False,
        }

        config2 = {
            "name": "component2",
            "graph_cache": False,
        }

        comp1 = MockComponent(**config1)
        comp2 = MockComponent(**config2)

        # Both components should have their own internal component managers
        assert comp1._internal_component_manager is not comp2._internal_component_manager