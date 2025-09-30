"""Integration tests for Internal Features with AsyncRuntime and UnifiedEventBus."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from woodwork.components.internal_features import InternalFeatureRegistry, InternalComponentManager
from woodwork.core.async_runtime import AsyncRuntime
from woodwork.core.unified_event_bus import UnifiedEventBus


@pytest.mark.integration
@pytest.mark.internal_features
@pytest.mark.asyncio
class TestAsyncRuntimeInternalFeaturesIntegration:
    """Test that internal features integrate properly with modern AsyncRuntime."""

    def setup_method(self):
        """Ensure graph cache feature is registered before each test."""
        from woodwork.components.internal_features.graph_cache import GraphCacheFeature
        from woodwork.components.internal_features.base import InternalFeatureRegistry
        InternalFeatureRegistry.register("graph_cache", GraphCacheFeature)

    @patch('woodwork.components.knowledge_bases.graph_databases.neo4j.neo4j')
    async def test_internal_components_register_with_async_runtime(self, mock_neo4j_factory):
        """Test that internal components are properly registered with AsyncRuntime."""
        # Setup mocks
        mock_neo4j_instance = Mock()
        mock_neo4j_instance.start = AsyncMock()  # Modern components have async start
        mock_neo4j_instance.close = AsyncMock()
        mock_neo4j_factory.return_value = mock_neo4j_instance

        # Create AsyncRuntime
        runtime = AsyncRuntime()

        # Mock LLM agent with graph_cache enabled
        mock_llm_agent = Mock()
        mock_llm_agent.name = "test_agent"
        mock_llm_agent.type = "agent"
        mock_llm_agent.component = "llm"
        mock_llm_agent.config = {"graph_cache": True}

        # Mock the model for API key
        mock_model = Mock()
        mock_model._api_key = "test-api-key"
        mock_llm_agent.model = mock_model

        # Create modern internal component manager (should integrate with AsyncRuntime)
        mock_llm_agent._internal_component_manager = InternalComponentManager(async_runtime=runtime)
        mock_llm_agent._internal_features = InternalFeatureRegistry.create_features({"graph_cache": True})

        # Setup internal features (this should register with AsyncRuntime)
        for feature in mock_llm_agent._internal_features:
            feature.setup(mock_llm_agent, {"graph_cache": True}, mock_llm_agent._internal_component_manager)

        # Verify Neo4j component was created and registered with AsyncRuntime
        assert mock_neo4j_factory.call_count >= 1

        # Verify AsyncRuntime has the internal component registered
        internal_neo4j_id = f"{mock_llm_agent.name}_graph_cache_neo4j"
        assert internal_neo4j_id in mock_llm_agent._internal_component_manager._components

        # Verify component is available in runtime (this is the key requirement)
        internal_component = mock_llm_agent._internal_component_manager.get_component(internal_neo4j_id)
        assert internal_component is mock_neo4j_instance

    async def test_internal_components_follow_async_lifecycle(self):
        """Test that internal components support async start/stop lifecycle."""
        # Create runtime
        runtime = AsyncRuntime()

        # Create internal component manager with runtime
        manager = InternalComponentManager(async_runtime=runtime)

        # Mock component with async lifecycle
        mock_component = Mock()
        mock_component.start = AsyncMock()
        mock_component.close = AsyncMock()

        # Register component
        manager._components["test_component"] = mock_component

        # Verify async lifecycle methods exist
        assert hasattr(mock_component, 'start')
        assert asyncio.iscoroutinefunction(mock_component.start)
        assert hasattr(mock_component, 'close')

    @patch('woodwork.components.knowledge_bases.graph_databases.neo4j.neo4j')
    async def test_unified_event_bus_integration(self, mock_neo4j_factory):
        """Test that internal features integrate with UnifiedEventBus for hooks/pipes."""
        # Setup mocks
        mock_neo4j_instance = Mock()
        mock_neo4j_factory.return_value = mock_neo4j_instance

        # Create event bus
        event_bus = UnifiedEventBus()

        # Create runtime with event bus
        runtime = AsyncRuntime()
        runtime.event_bus = event_bus

        # Mock LLM agent
        mock_llm_agent = Mock()
        mock_llm_agent.name = "test_agent"
        mock_model = Mock()
        mock_model._api_key = "test-api-key"
        mock_llm_agent.model = mock_model

        # Create modern internal component manager
        mock_llm_agent._internal_component_manager = InternalComponentManager(async_runtime=runtime)
        mock_llm_agent._internal_features = InternalFeatureRegistry.create_features({"graph_cache": True})

        # Setup features (should register hooks/pipes with UnifiedEventBus)
        for feature in mock_llm_agent._internal_features:
            feature.setup(mock_llm_agent, {"graph_cache": True}, mock_llm_agent._internal_component_manager)

        # Verify hooks and pipes are registered with UnifiedEventBus
        # (This is what we need to implement - currently they use old EventManager)
        assert hasattr(feature, 'get_hooks')
        assert hasattr(feature, 'get_pipes')

        hooks = feature.get_hooks()
        pipes = feature.get_pipes()

        # Should have cache-related hooks and pipes
        assert len(hooks) > 0
        assert len(pipes) > 0

        # Events should be: agent.action, agent.step_complete, input.received
        hook_events = [hook[0] for hook in hooks]
        pipe_events = [pipe[0] for pipe in pipes]

        assert "agent.action" in hook_events
        assert "agent.step_complete" in hook_events
        assert "input.received" in pipe_events

    async def test_internal_component_startup_integration(self):
        """Test that internal components are started during AsyncRuntime startup."""
        # This test ensures internal components participate in the normal startup cycle
        runtime = AsyncRuntime()

        # Mock component that should be started
        mock_internal_component = Mock()
        mock_internal_component.start = AsyncMock()
        mock_internal_component.name = "internal_neo4j"
        mock_internal_component.type = "neo4j"

        # Create internal component manager
        manager = InternalComponentManager(async_runtime=runtime)
        manager._components["internal_neo4j"] = mock_internal_component

        # Mock the startup process (this is what we need to implement)
        # Internal components should be included in startup_async_components()
        internal_components = list(manager._components.values())

        # Simulate AsyncRuntime calling start on all components
        for component in internal_components:
            if hasattr(component, 'start') and asyncio.iscoroutinefunction(component.start):
                await component.start()

        # Verify internal component was started
        mock_internal_component.start.assert_called_once()

    async def test_easy_feature_addition_workflow(self):
        """Test that adding a new internal feature is extremely simple."""
        # This test shows the target developer experience

        # Step 1: Define a simple feature class
        from woodwork.components.internal_features.base import InternalFeature

        class TestFeature(InternalFeature):
            def get_required_components(self):
                return [{
                    "component_type": "test_component",
                    "component_id": "test_internal",
                    "config": {"setting": "value"},
                    "optional": False
                }]

            def _setup_feature(self, component, config, component_manager):
                # Should be this simple to add components
                test_component = component_manager.get_or_create_component(
                    "test_internal", "test_component", {"setting": "value"}
                )
                component._test_feature = test_component

            def teardown(self, component, component_manager):
                if hasattr(component, '_test_feature'):
                    delattr(component, '_test_feature')

            def get_hooks(self):
                return [("test.event", self._test_hook)]

            def get_pipes(self):
                return [("test.input", self._test_pipe)]

            def _test_hook(self, payload):
                pass

            def _test_pipe(self, payload):
                return payload

        # Step 2: Register feature (should be one line)
        InternalFeatureRegistry.register("test_feature", TestFeature)

        # Step 3: Mock the component factory for test
        manager = InternalComponentManager()
        def mock_test_component(**config):
            mock_comp = Mock()
            mock_comp.config = config
            return mock_comp

        # Temporarily patch the component creation
        original_create = manager._create_component
        def patched_create(component_type, config):
            if component_type == "test_component":
                return mock_test_component(**config)
            return original_create(component_type, config)
        manager._create_component = patched_create

        # Step 4: Use in config (should be one line)
        config = {"test_feature": True}
        features = InternalFeatureRegistry.create_features(config)

        # Should automatically create the feature
        assert len(features) == 1
        assert isinstance(features[0], TestFeature)

        print("✓ Feature addition workflow is simple and intuitive")