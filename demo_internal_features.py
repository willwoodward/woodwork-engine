#!/usr/bin/env python3
"""
Demo script showing the Internal Features system in action.

This demonstrates how the `graph_cache: true` configuration flag
automatically creates a Neo4j component and sets up graph caching
functionality without manual configuration.
"""

from unittest.mock import Mock, patch
from woodwork.components.internal_features import InternalFeatureRegistry
from woodwork.components.internal_features.graph_cache import GraphCacheFeature


def demo_basic_registration():
    """Demo: Basic feature registration and discovery."""
    print("=== Internal Feature Registration Demo ===")

    # Show registered features
    features = InternalFeatureRegistry.get_registered_features()
    print(f"Registered features: {list(features.keys())}")

    # Show feature creation based on config
    config_with_cache = {"graph_cache": True, "other_setting": "value"}
    enabled_features = InternalFeatureRegistry.create_features(config_with_cache)
    print(f"Features created with graph_cache=True: {len(enabled_features)}")

    config_without_cache = {"graph_cache": False, "other_setting": "value"}
    disabled_features = InternalFeatureRegistry.create_features(config_without_cache)
    print(f"Features created with graph_cache=False: {len(disabled_features)}")
    print()


def demo_graph_cache_feature():
    """Demo: GraphCacheFeature auto-component creation."""
    print("=== Graph Cache Feature Demo ===")

    # Create a feature instance
    feature = GraphCacheFeature()

    # Show required components
    required = feature.get_required_components()
    print(f"Required components: {len(required)}")
    for comp_spec in required:
        print(f"  - {comp_spec['component_type']}: {comp_spec['component_id']}")

    # Show hooks and pipes
    hooks = feature.get_hooks()
    pipes = feature.get_pipes()
    print(f"Hooks registered: {[event for event, _ in hooks]}")
    print(f"Pipes registered: {[event for event, _ in pipes]}")
    print()


@patch('woodwork.components.knowledge_bases.graph_databases.neo4j.neo4j')
def demo_component_integration(mock_neo4j):
    """Demo: Full component integration with auto-created Neo4j."""
    print("=== Component Integration Demo ===")

    # Mock Neo4j component
    mock_neo4j_instance = Mock()
    mock_neo4j.return_value = mock_neo4j_instance

    # Import the component manager and feature
    from woodwork.components.internal_features import InternalComponentManager

    # Create component manager (simulating component initialization)
    manager = InternalComponentManager()

    # Create feature and set it up
    feature = GraphCacheFeature()

    # Mock component with model
    mock_component = Mock()
    mock_component.name = "demo_agent"
    mock_model = Mock()
    mock_model._api_key = "demo-api-key"
    mock_component.model = mock_model

    # Setup feature (this would normally happen automatically)
    config = {"graph_cache": True}
    feature.setup(mock_component, config, manager)

    # Verify Neo4j component was created
    print(f"Neo4j component created: {mock_neo4j.called}")
    if mock_neo4j.called:
        call_kwargs = mock_neo4j.call_args[1]
        print(f"  API key: {call_kwargs.get('api_key', 'NOT_SET')}")
        print(f"  Database name: {call_kwargs.get('name', 'NOT_SET')}")

    # Verify component has cache attributes
    print(f"Component has _graph_cache: {hasattr(mock_component, '_graph_cache')}")
    print(f"Component has _cache_mode: {hasattr(mock_component, '_cache_mode')}")

    # Test cleanup
    feature.teardown(mock_component, manager)
    manager.cleanup_components()
    print(f"Neo4j close called: {mock_neo4j_instance.close.called}")
    print()


def demo_configuration_examples():
    """Demo: Configuration examples for different scenarios."""
    print("=== Configuration Examples ===")

    # Example 1: Basic graph cache
    print("Example 1 - Basic graph cache:")
    config1 = {"graph_cache": True}
    features1 = InternalFeatureRegistry.create_features(config1)
    print(f"  Config: {config1}")
    print(f"  Features created: {len(features1)}")

    # Example 2: Custom graph cache settings
    print("\nExample 2 - Custom graph cache settings:")
    config2 = {
        "graph_cache": True,
        "graph_cache_uri": "bolt://custom-neo4j:7687",
        "graph_cache_user": "custom_user",
        "graph_cache_password": "custom_pass"
    }
    features2 = InternalFeatureRegistry.create_features(config2)
    print(f"  Config keys: {list(config2.keys())}")
    print(f"  Features created: {len(features2)}")

    # Example 3: Multiple features (when more are added)
    print("\nExample 3 - Multiple internal features:")
    config3 = {
        "graph_cache": True,
        "vector_memory": False,  # Future feature
        "telemetry": False,      # Future feature
    }
    features3 = InternalFeatureRegistry.create_features(config3)
    print(f"  Config: {config3}")
    print(f"  Features created: {len(features3)}")
    print()


if __name__ == "__main__":
    print("Internal Features System Demo")
    print("============================\n")

    demo_basic_registration()
    demo_graph_cache_feature()
    demo_component_integration()
    demo_configuration_examples()

    print("Demo completed successfully!")
    print("\nKey Benefits:")
    print("1. Declarative configuration: Just set `graph_cache: true`")
    print("2. Auto-component creation: Neo4j component created automatically")
    print("3. Clean separation: Internal features separate from user hooks/pipes")
    print("4. Extensible: Easy to add new features like `vector_memory: true`")
    print("5. Type safe: All hooks/pipes are strongly typed")
    print("6. Resource management: Automatic cleanup prevents resource leaks")