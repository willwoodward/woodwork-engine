"""Unit tests for InternalComponentManager."""

import pytest
from unittest.mock import Mock, patch
from woodwork.components.internal_features import InternalComponentManager


@pytest.mark.unit
@pytest.mark.internal_features
class TestInternalComponentManager:
    @pytest.fixture
    def component_manager(self):
        return InternalComponentManager()

    def test_init_default(self, component_manager):
        """Test component manager initializes properly with default settings."""
        assert component_manager._components == {}
        assert hasattr(component_manager, "_async_runtime")
        assert component_manager._async_runtime is None

    def test_init_with_runtime(self):
        """Test component manager accepts an external runtime."""
        mock_runtime = Mock()
        manager = InternalComponentManager(async_runtime=mock_runtime)
        assert manager._async_runtime is mock_runtime

    @patch("woodwork.components.knowledge_bases.graph_databases.neo4j.Neo4j")
    def test_create_neo4j_component(self, mock_neo4j_factory, component_manager):
        """Test creating Neo4j component."""
        mock_neo4j_instance = Mock()
        mock_neo4j_factory.return_value = mock_neo4j_instance

        config = {"uri": "bolt://localhost:7687", "user": "neo4j", "password": "test"}
        component = component_manager.get_or_create_component("test_neo4j", "neo4j", config)

        mock_neo4j_factory.assert_called_once_with(**config)
        assert component is mock_neo4j_instance
        assert component_manager.get_component("test_neo4j") is mock_neo4j_instance

    def test_create_unknown_component_type(self, component_manager):
        """Test creating unknown component type raises error."""
        with pytest.raises(ValueError, match="Unknown internal component type"):
            component_manager.get_or_create_component("test_unknown", "unknown_type", {})

    def test_get_existing_component(self, component_manager):
        """Test retrieving existing component."""
        mock_component = Mock()
        component_manager._components["existing"] = mock_component
        assert component_manager.get_component("existing") is mock_component

    def test_get_nonexistent_component(self, component_manager):
        assert component_manager.get_component("nonexistent") is None

    @patch("woodwork.components.knowledge_bases.graph_databases.neo4j.Neo4j")
    def test_get_or_create_returns_existing(self, mock_neo4j_factory, component_manager):
        """get_or_create returns existing component without creating new one."""
        mock_component = Mock()
        component_manager._components["existing"] = mock_component

        result = component_manager.get_or_create_component("existing", "neo4j", {"uri": "bolt://localhost:7687"})

        assert result is mock_component
        mock_neo4j_factory.assert_not_called()

    def test_cleanup_components(self, component_manager):
        """Cleanup calls close() on each component."""
        m1, m2 = Mock(), Mock()
        component_manager._components = {"t1": m1, "t2": m2}
        component_manager.cleanup_components()

        m1.close.assert_called_once()
        m2.close.assert_called_once()
        assert len(component_manager._components) == 0

    def test_cleanup_handles_exceptions(self, component_manager):
        mock_comp = Mock()
        mock_comp.close.side_effect = Exception("oops")
        component_manager._components["t"] = mock_comp
        component_manager.cleanup_components()  # should not raise
        assert len(component_manager._components) == 0

    def test_cleanup_without_close_method(self, component_manager):
        mock_comp = Mock(spec=[])
        component_manager._components["t"] = mock_comp
        component_manager.cleanup_components()  # should not raise
        assert len(component_manager._components) == 0

    @patch("woodwork.components.knowledge_bases.graph_databases.neo4j.Neo4j")
    def test_no_registration_when_no_runtime(self, mock_neo4j_factory):
        """Components are created but not registered when no runtime."""
        manager = InternalComponentManager()
        mock_instance = Mock()
        mock_neo4j_factory.return_value = mock_instance

        component = manager.get_or_create_component("test_neo4j", "neo4j", {"uri": "bolt://localhost:7687"})

        assert component is mock_instance
        assert "test_neo4j" in manager._components

    @patch("woodwork.components.knowledge_bases.graph_databases.neo4j.Neo4j")
    def test_register_with_runtime(self, mock_neo4j_factory):
        """Components are registered with runtime if it has register_internal_component."""
        mock_runtime = Mock()
        manager = InternalComponentManager(async_runtime=mock_runtime)
        mock_instance = Mock()
        mock_neo4j_factory.return_value = mock_instance

        manager.get_or_create_component("test_neo4j", "neo4j", {"uri": "bolt://localhost:7687"})

        mock_runtime.register_internal_component.assert_called_once_with("test_neo4j", mock_instance)
