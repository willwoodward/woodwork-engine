# Technical Design: Standardized Internal Hooks, Pipes, and Component Auto-Creation System

## Overview

This document outlines the design for a standardized system to automatically register internal hooks and pipes, and create internal components based on component configuration flags (like `graph_cache: true`). The goal is to provide a clean, testable way for components to automatically wire up additional functionality and internal components without manual configuration or dependency management.

## Current State Analysis

### Existing Architecture
- **Event System**: Mature typed event system with hooks (read-only, concurrent) and pipes (transformative, sequential)
- **Component Registration**: Components currently register user-defined hooks/pipes via `_setup_event_system()` during initialization
- **Agent Cache Pattern**: Agent components already have a manual cache implementation that creates Neo4j connections when `cache: true` is configured

### Key Findings
1. **Manual Cache Setup**: Agents manually initialize Neo4j cache in `__init__` method (`woodwork/components/agents/agent.py:51-61`)
2. **Component Lifecycle**: Components have predictable initialization flow with `_setup_event_system()` hook points
3. **Event Attribution**: Robust `EventSource` system for component-scoped events
4. **Typed Payloads**: Strong type safety with `BasePayload` subclasses and validation

## Design Goals

1. **Declarative Configuration**: Enable `graph_cache: true` style flags to automatically wire up internal functionality and components
2. **Auto-Component Creation**: Automatically create and register internal components when needed by features
3. **Clean Separation**: Keep internal hooks/pipes and components separate from user-defined ones
4. **Test-Driven**: Design for easy unit testing and mocking
5. **Extensible**: Support future internal features beyond graph caching
6. **Type Safe**: Maintain existing type safety guarantees
7. **Dependency Management**: Handle internal component dependencies automatically

## Proposed Architecture

### 1. Internal Feature Registry with Component Management

```python
# woodwork/components/internal_features.py
from typing import Dict, List, Callable, Type, Optional, Any
from abc import ABC, abstractmethod

class InternalFeature(ABC):
    """Base class for internal features that can be auto-wired to components."""

    @abstractmethod
    def setup(self, component: 'component', config: Dict, component_manager: 'InternalComponentManager') -> None:
        """Setup the feature for the given component."""
        pass

    @abstractmethod
    def teardown(self, component: 'component', component_manager: 'InternalComponentManager') -> None:
        """Clean up the feature when component closes."""
        pass

    @abstractmethod
    def get_hooks(self) -> List[Tuple[str, Callable]]:
        """Return list of (event_name, hook_function) tuples."""
        pass

    @abstractmethod
    def get_pipes(self) -> List[Tuple[str, Callable]]:
        """Return list of (event_name, pipe_function) tuples."""
        pass

    @abstractmethod
    def get_required_components(self) -> List[Dict[str, Any]]:
        """Return list of component specs this feature requires.

        Each spec is a dict with:
        - component_type: str (e.g., 'neo4j', 'chroma')
        - component_id: str (unique identifier)
        - config: Dict (component configuration)
        - optional: bool (whether component is optional, default False)
        """
        pass

class InternalComponentManager:
    """Manages auto-created internal components for features."""

    def __init__(self, task_master=None):
        self._components: Dict[str, Any] = {}
        self._task_master = task_master

    def get_or_create_component(self, component_id: str, component_type: str, config: Dict) -> Any:
        """Get existing component or create new one if not exists."""
        if component_id in self._components:
            return self._components[component_id]

        component = self._create_component(component_type, config)
        self._components[component_id] = component

        # Register with task master if available
        if self._task_master and hasattr(self._task_master, 'register_internal_component'):
            self._task_master.register_internal_component(component_id, component)

        return component

    def _create_component(self, component_type: str, config: Dict) -> Any:
        """Create component instance based on type."""
        from woodwork.components.knowledge_bases.graph_databases.neo4j import neo4j
        from woodwork.components.knowledge_bases.vector_databases.chroma import chroma

        component_factories = {
            'neo4j': neo4j,
            'chroma': chroma,
            # Add more component types as needed
        }

        if component_type not in component_factories:
            raise ValueError(f"Unknown internal component type: {component_type}")

        factory = component_factories[component_type]
        return factory(**config)

    def get_component(self, component_id: str) -> Optional[Any]:
        """Get existing component by ID."""
        return self._components.get(component_id)

    def cleanup_components(self) -> None:
        """Clean up all managed components."""
        for component in self._components.values():
            if hasattr(component, 'close'):
                component.close()
        self._components.clear()

class InternalFeatureRegistry:
    """Registry mapping config flags to internal features."""

    _features: Dict[str, Type[InternalFeature]] = {}

    @classmethod
    def register(cls, config_key: str, feature_class: Type[InternalFeature]):
        """Register a feature class for a config key."""
        cls._features[config_key] = feature_class

    @classmethod
    def create_features(cls, config: Dict) -> List[InternalFeature]:
        """Create feature instances based on config flags."""
        features = []
        for key, feature_class in cls._features.items():
            if config.get(key, False):
                features.append(feature_class())
        return features
```

### 2. Graph Cache Feature Implementation with Auto-Component Creation

```python
# woodwork/components/internal_features/graph_cache.py
from woodwork.components.internal_features import InternalFeature, InternalComponentManager
from woodwork.types import AgentActionPayload, AgentStepCompletePayload, InputReceivedPayload
from typing import Dict, List, Tuple, Callable, Any

class GraphCacheFeature(InternalFeature):
    """Internal feature for automatic graph caching with auto-created Neo4j component."""

    def __init__(self):
        self._neo4j_component = None
        self._component_ref = None

    def get_required_components(self) -> List[Dict[str, Any]]:
        """Define required Neo4j component for graph caching."""
        return [
            {
                "component_type": "neo4j",
                "component_id": "graph_cache_neo4j",
                "config": {
                    "uri": "bolt://localhost:7687",
                    "user": "neo4j",
                    "password": "testpassword",
                    "name": "graph_cache_db"
                },
                "optional": False
            }
        ]

    def setup(self, component: 'component', config: Dict, component_manager: InternalComponentManager) -> None:
        """Initialize graph cache with auto-created Neo4j component."""
        self._component_ref = component

        # Get API key from model (existing pattern)
        api_key = self._extract_api_key(component)
        if not api_key:
            raise TypeError("Graph cache requires API key from model configuration.")

        # Get or create Neo4j component through component manager
        neo4j_config = {
            "uri": config.get("graph_cache_uri", "bolt://localhost:7687"),
            "user": config.get("graph_cache_user", "neo4j"),
            "password": config.get("graph_cache_password", "testpassword"),
            "name": f"{component.name}_cache",
            "api_key": api_key
        }

        self._neo4j_component = component_manager.get_or_create_component(
            component_id=f"{component.name}_graph_cache_neo4j",
            component_type="neo4j",
            config=neo4j_config
        )

        # Initialize vector index if not already done
        try:
            self._neo4j_component.init_vector_index(
                index_name="embeddings",
                label="Prompt",
                property="embedding"
            )
        except Exception as e:
            # Index might already exist, which is fine
            pass

        # Attach to component for access
        component._graph_cache = self._neo4j_component
        component._cache_mode = True

    def teardown(self, component: 'component', component_manager: InternalComponentManager) -> None:
        """Clean up graph cache (component manager handles Neo4j cleanup)."""
        # Remove references from component
        if hasattr(component, '_graph_cache'):
            delattr(component, '_graph_cache')
        if hasattr(component, '_cache_mode'):
            delattr(component, '_cache_mode')

        # Component manager will handle actual Neo4j component cleanup
        self._neo4j_component = None

    def get_hooks(self) -> List[Tuple[str, Callable]]:
        """Return cache-related hooks."""
        return [
            ("agent.action", self._log_action_hook),
            ("agent.step_complete", self._cache_workflow_hook)
        ]

    def get_pipes(self) -> List[Tuple[str, Callable]]:
        """Return cache-related pipes."""
        return [
            ("input.received", self._check_cache_pipe)
        ]

    def _extract_api_key(self, component) -> str:
        """Extract API key from component's model."""
        if hasattr(component, 'model') and hasattr(component.model, '_api_key'):
            return component.model._api_key
        return None

    def _check_cache_pipe(self, payload: InputReceivedPayload) -> InputReceivedPayload:
        """Check cache for similar queries and potentially modify input."""
        if not self._neo4j_component:
            return payload

        try:
            # Implementation for cache lookup
            similar_results = self._neo4j_component.similarity_search(
                payload.input, "Prompt", "value"
            )

            if similar_results and similar_results[0].get("score", 0) > 0.9:
                # High confidence cache hit - could modify payload or set flag
                payload.cache_hit = True
                payload.cached_actions = self._extract_cached_actions(similar_results[0])
        except Exception as e:
            # Cache lookup failed, continue without cache
            pass

        return payload

    def _extract_cached_actions(self, result: Dict) -> List[str]:
        """Extract cached actions from similarity search result."""
        return result.get("actions", [])

    def _log_action_hook(self, payload: AgentActionPayload) -> None:
        """Log actions for future caching."""
        if not self._neo4j_component:
            return

        try:
            # Store action in graph for future cache hits
            self._neo4j_component.create_node(
                "Action",
                {
                    "action": payload.action,
                    "component_id": payload.component_id,
                    "timestamp": payload.timestamp if hasattr(payload, 'timestamp') else None
                }
            )
        except Exception as e:
            # Action logging failed, continue without error
            pass

    def _cache_workflow_hook(self, payload: AgentStepCompletePayload) -> None:
        """Cache completed workflow."""
        if not self._neo4j_component:
            return

        try:
            # Store completed workflow for future retrieval
            self._neo4j_component.create_node(
                "Workflow",
                {
                    "component_id": payload.component_id,
                    "result": payload.result if hasattr(payload, 'result') else None,
                    "timestamp": payload.timestamp if hasattr(payload, 'timestamp') else None
                }
            )
        except Exception as e:
            # Workflow caching failed, continue without error
            pass

# Register the feature
InternalFeatureRegistry.register("graph_cache", GraphCacheFeature)
```

### 3. Component Integration with Auto-Component Management

```python
# Modification to woodwork/components/component.py
class component:
    def __init__(self, **config):
        # ... existing initialization

        # Create internal component manager
        task_master = config.get('task_m', None)
        self._internal_component_manager = InternalComponentManager(task_master)

        # Setup internal features before user hooks/pipes
        self._internal_features = InternalFeatureRegistry.create_features(config)
        self._setup_internal_features(config)

        # Existing user hooks/pipes setup
        self._setup_event_system(config)

    def _setup_internal_features(self, config: Dict) -> None:
        """Setup internal features, create required components, and register hooks/pipes."""
        for feature in self._internal_features:
            # Create required components for this feature
            self._create_required_components(feature)

            # Setup the feature with component manager access
            feature.setup(self, config, self._internal_component_manager)

            # Register feature hooks
            for event_name, hook_func in feature.get_hooks():
                self._register_internal_hook(event_name, hook_func)

            # Register feature pipes
            for event_name, pipe_func in feature.get_pipes():
                self._register_internal_pipe(event_name, pipe_func)

    def _create_required_components(self, feature: InternalFeature) -> None:
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
                # Log warning for optional components that fail to create

    def _register_internal_hook(self, event: str, func: Callable) -> None:
        """Register internal hook with both event systems."""
        from woodwork.events import add_hook

        # Register with global event system
        add_hook(event, func)

        # Register with component-scoped system if it exists
        if hasattr(self, '_component_hooks'):
            if event not in self._component_hooks:
                self._component_hooks[event] = []
            self._component_hooks[event].append(func)

    def _register_internal_pipe(self, event: str, func: Callable) -> None:
        """Register internal pipe with both event systems."""
        from woodwork.events import add_pipe

        # Register with global event system
        add_pipe(event, func)

        # Register with component-scoped system if it exists
        if hasattr(self, '_component_pipes'):
            if event not in self._component_pipes:
                self._component_pipes[event] = []
            self._component_pipes[event].append(func)

    def get_internal_component(self, component_id: str):
        """Get an internal component by ID."""
        return self._internal_component_manager.get_component(component_id)

    def close(self):
        """Clean up internal features and components."""
        # Teardown features first
        for feature in self._internal_features:
            feature.teardown(self, self._internal_component_manager)

        # Then cleanup all internal components
        self._internal_component_manager.cleanup_components()

        # ... existing cleanup
```

### 4. Enhanced Agent Configuration with Auto-Component Support

```python
# Example .ww configuration
my_agent = agent llm {
    model: gpt4_model
    tools: [tool1, tool2]
    graph_cache: true  # Automatically creates Neo4j component and wires up graph caching

    # Optional: Override default graph cache settings
    graph_cache_uri: "bolt://custom-neo4j:7687"
    graph_cache_user: "custom_user"
    graph_cache_password: "custom_pass"

    # User-defined hooks still work normally
    hooks: [
        {
            event: "agent.thought"
            script_path: "custom_hooks.py"
            function_name: "debug_thoughts"
        }
    ]
}

# Example with multiple internal features
advanced_agent = agent llm {
    model: gpt4_model
    tools: [tool1, tool2, tool3]

    # Multiple internal features - each creates required components automatically
    graph_cache: true          # Creates Neo4j component
    vector_memory: true        # Creates Chroma component (hypothetical feature)
    telemetry: true           # Creates telemetry logging component (hypothetical feature)

    # Custom configuration for internal components
    vector_memory_collection: "agent_memories"
    telemetry_endpoint: "http://metrics.internal:8080"
}
```

## Test-Driven Development Approach

### 1. Unit Test Structure with Component Management

```python
# tests/test_internal_features.py
import pytest
from unittest.mock import Mock, patch
from woodwork.components.internal_features import InternalFeatureRegistry, InternalComponentManager
from woodwork.components.internal_features.graph_cache import GraphCacheFeature

class TestInternalComponentManager:
    @pytest.fixture
    def component_manager(self):
        return InternalComponentManager()

    @patch('woodwork.components.knowledge_bases.graph_databases.neo4j.neo4j')
    def test_create_neo4j_component(self, mock_neo4j_factory, component_manager):
        """Test creating Neo4j component."""
        config = {"uri": "bolt://localhost:7687", "user": "neo4j", "password": "test"}

        component = component_manager.get_or_create_component(
            "test_neo4j", "neo4j", config
        )

        mock_neo4j_factory.assert_called_once_with(**config)
        assert component_manager.get_component("test_neo4j") is not None

    def test_get_existing_component(self, component_manager):
        """Test retrieving existing component."""
        mock_component = Mock()
        component_manager._components["existing"] = mock_component

        result = component_manager.get_component("existing")
        assert result is mock_component

    def test_cleanup_components(self, component_manager):
        """Test component cleanup calls close() method."""
        mock_component = Mock()
        component_manager._components["test"] = mock_component

        component_manager.cleanup_components()

        mock_component.close.assert_called_once()
        assert len(component_manager._components) == 0

class TestGraphCacheFeature:
    @pytest.fixture
    def mock_component(self):
        component = Mock()
        component.name = "test_agent"
        model = Mock()
        model._api_key = "test-api-key"
        component.model = model
        return component

    @pytest.fixture
    def mock_component_manager(self):
        manager = Mock(spec=InternalComponentManager)
        mock_neo4j = Mock()
        manager.get_or_create_component.return_value = mock_neo4j
        return manager

    @pytest.fixture
    def graph_cache_feature(self):
        return GraphCacheFeature()

    def test_get_required_components(self, graph_cache_feature):
        """Test that feature specifies required Neo4j component."""
        required = graph_cache_feature.get_required_components()

        assert len(required) == 1
        assert required[0]["component_type"] == "neo4j"
        assert required[0]["component_id"] == "graph_cache_neo4j"
        assert not required[0]["optional"]

    def test_setup_creates_neo4j_component_via_manager(self, graph_cache_feature, mock_component, mock_component_manager):
        """Test that setup creates Neo4j component through component manager."""
        config = {"graph_cache": True}

        graph_cache_feature.setup(mock_component, config, mock_component_manager)

        # Verify component manager was called to create Neo4j component
        mock_component_manager.get_or_create_component.assert_called_once()
        call_args = mock_component_manager.get_or_create_component.call_args
        assert "neo4j" in call_args[1]["component_type"]

        assert hasattr(mock_component, '_graph_cache')
        assert mock_component._cache_mode is True

    def test_setup_requires_api_key(self, graph_cache_feature, mock_component_manager):
        """Test that setup fails without API key."""
        component = Mock()
        component.name = "test"
        component.model = Mock(spec=[])  # No _api_key attribute
        config = {"graph_cache": True}

        with pytest.raises(TypeError, match="Graph cache requires API key"):
            graph_cache_feature.setup(component, config, mock_component_manager)

    def test_teardown_removes_component_references(self, graph_cache_feature, mock_component, mock_component_manager):
        """Test that teardown removes component references but leaves cleanup to manager."""
        # Setup first
        config = {"graph_cache": True}
        graph_cache_feature.setup(mock_component, config, mock_component_manager)

        # Teardown
        graph_cache_feature.teardown(mock_component, mock_component_manager)

        assert not hasattr(mock_component, '_graph_cache')
        assert not hasattr(mock_component, '_cache_mode')

    def test_get_hooks_returns_expected_events(self, graph_cache_feature):
        """Test that feature registers expected hooks."""
        hooks = graph_cache_feature.get_hooks()

        hook_events = [event for event, _ in hooks]
        assert "agent.action" in hook_events
        assert "agent.step_complete" in hook_events

    def test_cache_pipe_modifies_payload_on_hit(self, graph_cache_feature):
        """Test that cache pipe modifies payload when cache hit occurs."""
        # Setup mock Neo4j component with high-confidence result
        mock_neo4j = Mock()
        mock_neo4j.similarity_search.return_value = [{"score": 0.95, "actions": ["cached_action"]}]
        graph_cache_feature._neo4j_component = mock_neo4j

        from woodwork.types import InputReceivedPayload
        payload = InputReceivedPayload(input="test query", inputs={}, session_id="test")

        result = graph_cache_feature._check_cache_pipe(payload)

        assert result.cache_hit is True
        assert hasattr(result, 'cached_actions')

class TestInternalFeatureRegistry:
    def test_register_and_create_features(self):
        """Test feature registration and creation."""
        # Register test feature
        test_feature_class = Mock()
        InternalFeatureRegistry.register("test_feature", test_feature_class)

        # Create features from config
        config = {"test_feature": True, "other_flag": False}
        features = InternalFeatureRegistry.create_features(config)

        test_feature_class.assert_called_once()
        assert len(features) == 1
```

### 2. Integration Tests with Component Auto-Creation

```python
# tests/test_agent_graph_cache_integration.py
import pytest
from unittest.mock import patch, Mock
from woodwork.components.agents.llm import llm
from woodwork.types import InputReceivedPayload

class TestAgentGraphCacheIntegration:
    @pytest.fixture
    def mock_task_master(self):
        task_master = Mock()
        task_master.register_internal_component = Mock()
        return task_master

    @pytest.fixture
    def mock_llm_model(self):
        model = Mock()
        model._api_key = "test-api-key"
        return model

    @patch('woodwork.components.knowledge_bases.graph_databases.neo4j.neo4j')
    def test_graph_cache_auto_created_and_wired(self, mock_neo4j_factory, mock_llm_model, mock_task_master):
        """Test that graph cache and Neo4j component are automatically created and wired."""
        mock_neo4j_instance = Mock()
        mock_neo4j_factory.return_value = mock_neo4j_instance

        config = {
            "model": mock_llm_model,
            "tools": [],
            "graph_cache": True,
            "name": "test_agent",
            "task_m": mock_task_master
        }

        agent = llm(**config)

        # Verify Neo4j component was created
        mock_neo4j_factory.assert_called_once()
        call_kwargs = mock_neo4j_factory.call_args[1]
        assert call_kwargs["api_key"] == "test-api-key"
        assert "test_agent_cache" in call_kwargs["name"]

        # Verify agent has cache references
        assert hasattr(agent, '_graph_cache')
        assert agent._cache_mode is True
        assert agent._graph_cache is mock_neo4j_instance

        # Verify internal component manager was set up
        assert hasattr(agent, '_internal_component_manager')

    @patch('woodwork.components.knowledge_bases.graph_databases.neo4j.neo4j')
    def test_custom_graph_cache_config(self, mock_neo4j_factory, mock_llm_model, mock_task_master):
        """Test that custom graph cache configuration is respected."""
        config = {
            "model": mock_llm_model,
            "tools": [],
            "graph_cache": True,
            "graph_cache_uri": "bolt://custom:7687",
            "graph_cache_user": "custom_user",
            "graph_cache_password": "custom_pass",
            "name": "test_agent",
            "task_m": mock_task_master
        }

        agent = llm(**config)

        # Verify custom config was used
        call_kwargs = mock_neo4j_factory.call_args[1]
        assert call_kwargs["uri"] == "bolt://custom:7687"
        assert call_kwargs["user"] == "custom_user"
        assert call_kwargs["password"] == "custom_pass"

    def test_multiple_agents_share_components(self, mock_llm_model, mock_task_master):
        """Test that multiple agents can share internal components when appropriate."""
        with patch('woodwork.components.knowledge_bases.graph_databases.neo4j.neo4j') as mock_neo4j_factory:
            config_base = {
                "model": mock_llm_model,
                "tools": [],
                "graph_cache": True,
                "task_m": mock_task_master
            }

            agent1 = llm(name="agent1", **config_base)
            agent2 = llm(name="agent2", **config_base)

            # Both agents should have their own internal component managers
            assert agent1._internal_component_manager is not agent2._internal_component_manager

            # But they could potentially share components if configured to do so
            # (This depends on the specific implementation of component sharing)

    @patch('woodwork.events.emit')
    @patch('woodwork.components.knowledge_bases.graph_databases.neo4j.neo4j')
    def test_cache_hooks_automatically_registered(self, mock_neo4j_factory, mock_emit, mock_llm_model, mock_task_master):
        """Test that cache hooks are automatically registered and functional."""
        mock_neo4j_instance = Mock()
        mock_neo4j_factory.return_value = mock_neo4j_instance

        config = {
            "model": mock_llm_model,
            "tools": [],
            "graph_cache": True,
            "name": "test_agent",
            "task_m": mock_task_master
        }

        agent = llm(**config)

        # Simulate agent processing input
        agent.input("test query")

        # Verify cache-related events were processed
        # Note: Specific verification depends on how events flow through the system
        emitted_events = [call[0][0] for call in mock_emit.call_args_list]

        # Should include events that cache hooks listen to
        expected_events = {"agent.action", "agent.step_complete", "input.received"}
        assert any(event in expected_events for event in emitted_events)

    @patch('woodwork.components.knowledge_bases.graph_databases.neo4j.neo4j')
    def test_agent_cleanup_cleans_internal_components(self, mock_neo4j_factory, mock_llm_model, mock_task_master):
        """Test that agent cleanup properly cleans up internal components."""
        mock_neo4j_instance = Mock()
        mock_neo4j_factory.return_value = mock_neo4j_instance

        config = {
            "model": mock_llm_model,
            "tools": [],
            "graph_cache": True,
            "name": "test_agent",
            "task_m": mock_task_master
        }

        agent = llm(**config)

        # Close the agent
        agent.close()

        # Verify Neo4j component was closed
        mock_neo4j_instance.close.assert_called_once()

    def test_agent_access_to_internal_components(self, mock_llm_model, mock_task_master):
        """Test that agents can access their internal components when needed."""
        with patch('woodwork.components.knowledge_bases.graph_databases.neo4j.neo4j') as mock_neo4j_factory:
            mock_neo4j_instance = Mock()
            mock_neo4j_factory.return_value = mock_neo4j_instance

            config = {
                "model": mock_llm_model,
                "tools": [],
                "graph_cache": True,
                "name": "test_agent",
                "task_m": mock_task_master
            }

            agent = llm(**config)

            # Agent should be able to access internal Neo4j component
            neo4j_component = agent.get_internal_component("test_agent_graph_cache_neo4j")
            assert neo4j_component is mock_neo4j_instance
```

### 3. Test Configuration

```python
# tests/conftest.py
@pytest.fixture
def mock_neo4j():
    """Mock Neo4j component for testing."""
    with patch('woodwork.components.knowledge_bases.graph_databases.neo4j.neo4j') as mock:
        mock_instance = Mock()
        mock_instance.similarity_search.return_value = []
        mock.return_value = mock_instance
        yield mock_instance
```

## Implementation Benefits

### 1. **Clean Separation**
- Internal features and auto-created components are completely separate from user-defined ones
- No configuration pollution - `graph_cache: true` is clear and minimal
- Existing functionality remains unchanged

### 2. **Auto-Component Management**
- Components are created automatically when needed by features
- Shared component management prevents duplicate instances
- Automatic cleanup prevents resource leaks
- Components can be reused across multiple features

### 3. **Extensibility**
- New internal features (e.g., `memory_persistence: true`, `telemetry: true`) follow same pattern
- Easy to add new auto-wiring capabilities and component types
- Registry pattern supports runtime feature discovery
- Component factories can be extended for new component types

### 4. **Testability**
- Features and component manager are isolated and mockable
- Integration tests verify end-to-end component creation and wiring
- Clear dependency injection points for both features and components
- Component lifecycle is fully testable

### 5. **Type Safety**
- Maintains existing typed payload system
- Feature setup is type-checked
- Hook/pipe signatures remain strongly typed
- Component specifications are strongly typed

### 6. **Resource Management**
- Centralized component lifecycle management
- Automatic cleanup of internal components
- Prevention of resource leaks through proper teardown
- Optional components can fail gracefully without breaking features

## Migration Path

1. **Phase 1**: Implement `InternalFeature` base class, `InternalComponentManager`, and registry
2. **Phase 2**: Create `GraphCacheFeature` implementation with auto-component creation
3. **Phase 3**: Integrate with component initialization flow and add component management
4. **Phase 4**: Add comprehensive test suite covering both features and component management
5. **Phase 5**: Migrate existing manual cache logic to new system
6. **Phase 6**: Add support for additional component types (Chroma, etc.)
7. **Phase 7**: Implement additional internal features that leverage auto-component creation
8. **Phase 8**: Add documentation and examples

This enhanced design provides a clean, testable foundation for internal feature auto-wiring with automatic component creation, while maintaining backward compatibility and the existing architecture's strengths. The component management system ensures that internal dependencies are handled automatically and efficiently.