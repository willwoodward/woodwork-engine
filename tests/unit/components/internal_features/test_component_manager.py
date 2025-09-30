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

    @pytest.fixture
    def mock_task_master(self):
        task_master = Mock()
        task_master.register_internal_component = Mock()
        return task_master

    def test_init_default(self, component_manager):
        """Test component manager initializes properly with default settings."""
        assert component_manager._components == {}
        assert hasattr(component_manager, '_async_runtime')

    def test_init_with_async_runtime(self):
        """Test component manager initializes properly with AsyncRuntime."""
        from woodwork.core.async_runtime import AsyncRuntime

        mock_runtime = Mock(spec=AsyncRuntime)
        manager = InternalComponentManager(async_runtime=mock_runtime)
        assert manager._async_runtime is mock_runtime

    @patch('woodwork.components.knowledge_bases.graph_databases.neo4j.neo4j')
    def test_create_neo4j_component(self, mock_neo4j_factory, component_manager):
        """Test creating Neo4j component."""
        mock_neo4j_instance = Mock()
        mock_neo4j_factory.return_value = mock_neo4j_instance

        config = {"uri": "bolt://localhost:7687", "user": "neo4j", "password": "test"}

        component = component_manager.get_or_create_component(
            "test_neo4j", "neo4j", config
        )

        mock_neo4j_factory.assert_called_once_with(**config)
        assert component is mock_neo4j_instance
        assert component_manager.get_component("test_neo4j") is mock_neo4j_instance

    def test_create_unknown_component_type(self, component_manager):
        """Test creating unknown component type raises error."""
        config = {"collection_name": "test_collection"}

        with pytest.raises(ValueError, match="Unknown internal component type"):
            component_manager.get_or_create_component(
                "test_unknown", "unknown_type", config
            )

    def test_get_existing_component(self, component_manager):
        """Test retrieving existing component."""
        mock_component = Mock()
        component_manager._components["existing"] = mock_component

        result = component_manager.get_component("existing")
        assert result is mock_component

    def test_get_nonexistent_component(self, component_manager):
        """Test retrieving non-existent component returns None."""
        result = component_manager.get_component("nonexistent")
        assert result is None

    @patch('woodwork.components.knowledge_bases.graph_databases.neo4j.neo4j')
    def test_get_or_create_returns_existing(self, mock_neo4j_factory, component_manager):
        """Test that get_or_create returns existing component without creating new one."""
        mock_component = Mock()
        component_manager._components["existing"] = mock_component

        result = component_manager.get_or_create_component(
            "existing", "neo4j", {"uri": "bolt://localhost:7687"}
        )

        assert result is mock_component
        mock_neo4j_factory.assert_not_called()

    def test_unknown_component_type_raises_error(self, component_manager):
        """Test that unknown component type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown internal component type: unknown"):
            component_manager.get_or_create_component(
                "test", "unknown", {}
            )

    def test_cleanup_components(self, component_manager):
        """Test component cleanup calls close() method."""
        mock_component1 = Mock()
        mock_component2 = Mock()
        component_manager._components["test1"] = mock_component1
        component_manager._components["test2"] = mock_component2

        component_manager.cleanup_components()

        mock_component1.close.assert_called_once()
        mock_component2.close.assert_called_once()
        assert len(component_manager._components) == 0

    def test_cleanup_components_handles_exceptions(self, component_manager):
        """Test component cleanup handles exceptions gracefully."""
        mock_component = Mock()
        mock_component.close.side_effect = Exception("Close failed")
        component_manager._components["test"] = mock_component

        # Should not raise exception
        component_manager.cleanup_components()
        assert len(component_manager._components) == 0

    def test_cleanup_components_without_close_method(self, component_manager):
        """Test cleanup handles components without close method."""
        mock_component = Mock(spec=[])  # No close method
        component_manager._components["test"] = mock_component

        # Should not raise exception
        component_manager.cleanup_components()
        assert len(component_manager._components) == 0

    @patch('woodwork.components.knowledge_bases.graph_databases.neo4j.neo4j')
    @patch('woodwork.core.async_runtime.get_global_runtime')
    def test_no_registration_when_no_runtime(self, mock_get_runtime, mock_neo4j_factory):
        """Test that components are created but not registered when no AsyncRuntime is available."""
        # Mock global runtime to return None
        mock_get_runtime.side_effect = Exception("No global runtime")

        manager = InternalComponentManager()
        mock_neo4j_instance = Mock()
        mock_neo4j_factory.return_value = mock_neo4j_instance

        component = manager.get_or_create_component(
            "test_neo4j", "neo4j", {"uri": "bolt://localhost:7687"}
        )

        # Component should be created but not registered anywhere
        assert component is mock_neo4j_instance
        assert "test_neo4j" in manager._components

    @patch('woodwork.components.knowledge_bases.graph_databases.neo4j.neo4j')
    def test_register_with_async_runtime(self, mock_neo4j_factory):
        """Test that components are registered with AsyncRuntime by default."""
        from woodwork.core.async_runtime import AsyncRuntime

        mock_runtime = Mock(spec=AsyncRuntime)
        manager = InternalComponentManager(async_runtime=mock_runtime)
        mock_neo4j_instance = Mock()
        mock_neo4j_factory.return_value = mock_neo4j_instance

        component = manager.get_or_create_component(
            "test_neo4j", "neo4j", {"uri": "bolt://localhost:7687"}
        )

        mock_runtime.register_internal_component.assert_called_once_with(
            "test_neo4j", mock_neo4j_instance
        )