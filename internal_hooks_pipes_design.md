# Technical Design: Standardized Internal Hooks and Pipes System

## Overview

This document outlines the design for a standardized system to automatically register internal hooks and pipes based on component configuration flags (like `graph_cache: true`). The goal is to provide a clean, testable way for components to automatically wire up additional functionality without manual configuration.

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

1. **Declarative Configuration**: Enable `graph_cache: true` style flags to automatically wire up internal functionality
2. **Clean Separation**: Keep internal hooks/pipes separate from user-defined ones
3. **Test-Driven**: Design for easy unit testing and mocking
4. **Extensible**: Support future internal features beyond graph caching
5. **Type Safe**: Maintain existing type safety guarantees

## Proposed Architecture

### 1. Internal Feature Registry

```python
# woodwork/components/internal_features.py
from typing import Dict, List, Callable, Type
from abc import ABC, abstractmethod

class InternalFeature(ABC):
    """Base class for internal features that can be auto-wired to components."""

    @abstractmethod
    def setup(self, component: 'component', config: Dict) -> None:
        """Setup the feature for the given component."""
        pass

    @abstractmethod
    def teardown(self, component: 'component') -> None:
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

### 2. Graph Cache Feature Implementation

```python
# woodwork/components/internal_features/graph_cache.py
from woodwork.components.internal_features import InternalFeature
from woodwork.components.knowledge_bases.graph_databases.neo4j import neo4j
from woodwork.types import AgentActionPayload, AgentStepCompletePayload

class GraphCacheFeature(InternalFeature):
    """Internal feature for automatic graph caching."""

    def __init__(self):
        self._neo4j_component = None
        self._component_ref = None

    def setup(self, component: 'component', config: Dict) -> None:
        """Initialize Neo4j component and cache setup."""
        self._component_ref = component

        # Get API key from model (existing pattern)
        api_key = self._extract_api_key(component)
        if not api_key:
            raise TypeError("Graph cache requires API key from model configuration.")

        # Create Neo4j component
        self._neo4j_component = neo4j(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="testpassword",
            name=f"{component.name}_cache",
            api_key=api_key
        )

        # Initialize vector index
        self._neo4j_component.init_vector_index(
            index_name="embeddings",
            label="Prompt",
            property="embedding"
        )

        # Attach to component for access
        component._graph_cache = self._neo4j_component
        component._cache_mode = True

    def teardown(self, component: 'component') -> None:
        """Clean up Neo4j connection."""
        if self._neo4j_component:
            self._neo4j_component.close()

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

    def _check_cache_pipe(self, payload: InputReceivedPayload) -> InputReceivedPayload:
        """Check cache for similar queries and potentially modify input."""
        if not self._neo4j_component:
            return payload

        # Implementation for cache lookup
        similar_results = self._neo4j_component.similarity_search(
            payload.input, "Prompt", "value"
        )

        if similar_results and similar_results[0]["score"] > 0.9:
            # High confidence cache hit - could modify payload or set flag
            payload.cache_hit = True
            payload.cached_actions = self._extract_cached_actions(similar_results[0])

        return payload

    def _log_action_hook(self, payload: AgentActionPayload) -> None:
        """Log actions for future caching."""
        # Implementation for action logging
        pass

    def _cache_workflow_hook(self, payload: AgentStepCompletePayload) -> None:
        """Cache completed workflow."""
        # Implementation for workflow caching
        pass

# Register the feature
InternalFeatureRegistry.register("graph_cache", GraphCacheFeature)
```

### 3. Component Integration

```python
# Modification to woodwork/components/component.py
class component:
    def __init__(self, **config):
        # ... existing initialization

        # Setup internal features before user hooks/pipes
        self._internal_features = InternalFeatureRegistry.create_features(config)
        self._setup_internal_features(config)

        # Existing user hooks/pipes setup
        self._setup_event_system(config)

    def _setup_internal_features(self, config: Dict) -> None:
        """Setup internal features and register their hooks/pipes."""
        for feature in self._internal_features:
            feature.setup(self, config)

            # Register feature hooks
            for event_name, hook_func in feature.get_hooks():
                self._register_internal_hook(event_name, hook_func)

            # Register feature pipes
            for event_name, pipe_func in feature.get_pipes():
                self._register_internal_pipe(event_name, pipe_func)

    def _register_internal_hook(self, event: str, func: Callable) -> None:
        """Register internal hook with both event systems."""
        # Similar to existing _register_hooks_global but for internal hooks
        pass

    def _register_internal_pipe(self, event: str, func: Callable) -> None:
        """Register internal pipe with both event systems."""
        # Similar to existing _register_pipes_global but for internal pipes
        pass

    def close(self):
        """Clean up internal features."""
        for feature in self._internal_features:
            feature.teardown(self)

        # ... existing cleanup
```

### 4. Enhanced Agent Configuration

```python
# Example .ww configuration
my_agent = agent llm {
    model: gpt4_model
    tools: [tool1, tool2]
    graph_cache: true  # Automatically wires up graph caching

    # User-defined hooks still work normally
    hooks: [
        {
            event: "agent.thought"
            script_path: "custom_hooks.py"
            function_name: "debug_thoughts"
        }
    ]
}
```

## Test-Driven Development Approach

### 1. Unit Test Structure

```python
# tests/test_internal_features.py
import pytest
from unittest.mock import Mock, patch
from woodwork.components.internal_features import InternalFeatureRegistry
from woodwork.components.internal_features.graph_cache import GraphCacheFeature

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
    def graph_cache_feature(self):
        return GraphCacheFeature()

    @patch('woodwork.components.internal_features.graph_cache.neo4j')
    def test_setup_creates_neo4j_component(self, mock_neo4j, graph_cache_feature, mock_component):
        """Test that setup creates and configures Neo4j component."""
        config = {"graph_cache": True}

        graph_cache_feature.setup(mock_component, config)

        mock_neo4j.assert_called_once()
        assert hasattr(mock_component, '_graph_cache')
        assert mock_component._cache_mode is True

    def test_setup_requires_api_key(self, graph_cache_feature):
        """Test that setup fails without API key."""
        component = Mock()
        component.model = Mock(spec=[])  # No _api_key attribute
        config = {"graph_cache": True}

        with pytest.raises(TypeError, match="Graph cache requires API key"):
            graph_cache_feature.setup(component, config)

    def test_get_hooks_returns_expected_events(self, graph_cache_feature):
        """Test that feature registers expected hooks."""
        hooks = graph_cache_feature.get_hooks()

        hook_events = [event for event, _ in hooks]
        assert "agent.action" in hook_events
        assert "agent.step_complete" in hook_events

    def test_cache_pipe_modifies_payload_on_hit(self, graph_cache_feature, mock_component):
        """Test that cache pipe modifies payload when cache hit occurs."""
        # Setup mock cache with high-confidence result
        mock_neo4j = Mock()
        mock_neo4j.similarity_search.return_value = [{"score": 0.95, "actions": ["cached_action"]}]
        graph_cache_feature._neo4j_component = mock_neo4j

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

### 2. Integration Tests

```python
# tests/test_agent_graph_cache_integration.py
import pytest
from woodwork.components.agents.llm import llm
from woodwork.types import InputReceivedPayload

class TestAgentGraphCacheIntegration:
    @pytest.fixture
    def agent_with_graph_cache(self, mock_llm_model, mock_task_master):
        """Create agent with graph_cache enabled."""
        config = {
            "model": mock_llm_model,
            "tools": [],
            "graph_cache": True,
            "name": "test_agent"
        }
        return llm(tools=[], task_m=mock_task_master, **config)

    def test_graph_cache_auto_wired(self, agent_with_graph_cache):
        """Test that graph cache is automatically set up."""
        assert hasattr(agent_with_graph_cache, '_graph_cache')
        assert agent_with_graph_cache._cache_mode is True

    @patch('woodwork.events.emit')
    def test_cache_hooks_registered(self, mock_emit, agent_with_graph_cache):
        """Test that cache hooks are automatically registered."""
        # Trigger agent action that should emit events
        agent_with_graph_cache.input("test query")

        # Verify cache-related events were processed
        emitted_events = [call[0][0] for call in mock_emit.call_args_list]
        assert "agent.action" in emitted_events
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
- Internal features are completely separate from user hooks/pipes
- No configuration pollution - `graph_cache: true` is clear and minimal
- Existing functionality remains unchanged

### 2. **Extensibility**
- New internal features (e.g., `memory_persistence: true`, `telemetry: true`) follow same pattern
- Easy to add new auto-wiring capabilities
- Registry pattern supports runtime feature discovery

### 3. **Testability**
- Features are isolated and mockable
- Integration tests verify end-to-end wiring
- Clear dependency injection points

### 4. **Type Safety**
- Maintains existing typed payload system
- Feature setup is type-checked
- Hook/pipe signatures remain strongly typed

## Migration Path

1. **Phase 1**: Implement `InternalFeature` base class and registry
2. **Phase 2**: Create `GraphCacheFeature` implementation
3. **Phase 3**: Integrate with component initialization flow
4. **Phase 4**: Add comprehensive test suite
5. **Phase 5**: Migrate existing manual cache logic to new system
6. **Phase 6**: Add documentation and examples

This design provides a clean, testable foundation for internal feature auto-wiring while maintaining backward compatibility and the existing architecture's strengths.