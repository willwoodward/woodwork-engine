# Test Organization

This document describes the organization of tests in the Woodwork engine project.

## Directory Structure

```
tests/
├── unit/                           # Unit tests (fast, isolated)
│   └── components/
│       └── internal_features/     # Internal features system unit tests
│           ├── test_component_manager.py     # InternalComponentManager tests
│           ├── test_feature_registry.py      # InternalFeatureRegistry tests
│           ├── test_graph_cache_feature.py   # GraphCacheFeature tests
│           └── test_integration_features.py  # Feature integration tests
└── integration/                    # Integration tests (slower, may require setup)
    └── components/
        └── internal_features/      # Internal features system integration tests
            └── test_component_internal_features_integration.py

```

## Test Categories

### Unit Tests (`tests/unit/`)
- **Fast**: Run in milliseconds
- **Isolated**: Test single components in isolation
- **Mocked**: Use mocks for external dependencies
- **Focused**: Test specific functionality without dependencies

### Integration Tests (`tests/integration/`)
- **Slower**: May take seconds to run
- **Connected**: Test multiple components working together
- **Real Dependencies**: May use real or more complete mock setups
- **End-to-End**: Test complete workflows

## Test Markers

Tests are organized using pytest markers for easy filtering:

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.internal_features` - Tests related to internal features system
- `@pytest.mark.graph_cache` - Tests related to graph cache feature

## Running Tests

### Run All Tests
```bash
pytest
```

### Run by Category
```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# Internal features tests only
pytest -m internal_features

# Graph cache tests only
pytest -m graph_cache
```

### Run by Directory
```bash
# All unit tests
pytest tests/unit/

# All integration tests
pytest tests/integration/

# Internal features unit tests
pytest tests/unit/components/internal_features/

# Internal features integration tests
pytest tests/integration/components/internal_features/
```

### Combine Markers
```bash
# Unit tests for internal features
pytest -m "unit and internal_features"

# Integration tests for graph cache
pytest -m "integration and graph_cache"
```

## Test Files

### Unit Tests

#### `test_component_manager.py`
Tests for `InternalComponentManager` class:
- Component creation and management
- Task master integration
- Cleanup and error handling

#### `test_feature_registry.py`
Tests for `InternalFeatureRegistry` class:
- Feature registration and discovery
- Configuration-based feature creation
- Feature loading and imports

#### `test_graph_cache_feature.py`
Tests for `GraphCacheFeature` class:
- Feature setup and teardown
- Neo4j component creation
- Hooks and pipes functionality
- Configuration handling

#### `test_integration_features.py`
Tests for feature integration:
- Feature registration verification
- Feature creation from configuration
- Cross-feature functionality

### Integration Tests

#### `test_component_internal_features_integration.py`
End-to-end tests for the complete internal features system:
- Component initialization with features
- Full feature lifecycle (setup, operation, teardown)
- Component manager integration
- Error handling and graceful degradation

## Adding New Tests

### For New Features
1. Create unit tests in `tests/unit/components/internal_features/`
2. Create integration tests in `tests/integration/components/internal_features/`
3. Add appropriate markers (`@pytest.mark.unit`, `@pytest.mark.your_feature`)

### For New Components
1. Create new subdirectories under `tests/unit/components/` and `tests/integration/components/`
2. Follow the same naming convention: `test_[component_name].py`
3. Add appropriate markers for the component type

## Best Practices

1. **Unit tests should be fast** - Use mocks for external dependencies
2. **Integration tests should be realistic** - Test actual component interactions
3. **Use descriptive test names** - Test methods should describe what they test
4. **Group related tests** - Use test classes to group related functionality
5. **Use appropriate markers** - Mark tests correctly for easy filtering
6. **Clean setup/teardown** - Ensure tests don't interfere with each other