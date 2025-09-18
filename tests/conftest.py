"""Global pytest configuration and shared fixtures."""

import pytest
import asyncio
import logging
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

# Import fixtures from our test modules
from tests.unit.fixtures.mock_components import (
    MockComponent, MockAgent, MockTool, MockOutput, MockMessageBus, MockStream,
    create_test_components, create_mock_router
)
from tests.unit.fixtures.test_messages import (
    MockMessageEnvelope, create_component_message, create_response_message, create_hook_message
)
from tests.unit.fixtures.event_fixtures import (
    MockEventManager, MockPayload, create_test_event_data, create_mock_hooks, create_mock_pipes
)

# Configure logging for tests
logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_time():
    """Mock time.time() to return predictable values."""
    with patch('time.time', return_value=1000.0):
        yield 1000.0


@pytest.fixture
def deterministic_uuid():
    """Mock UUID generation for deterministic tests."""
    counter = 0

    def mock_uuid():
        nonlocal counter
        counter += 1
        mock_obj = Mock()
        mock_obj.hex = f"test_uuid_{counter:04d}"
        return mock_obj

    with patch('uuid.uuid4', side_effect=mock_uuid):
        yield


# Component Fixtures
@pytest.fixture
def mock_component():
    """Create a basic mock component."""
    return MockComponent("test_component", "test")


@pytest.fixture
def mock_agent():
    """Create a mock agent component."""
    return MockAgent("test_agent")


@pytest.fixture
def mock_tool():
    """Create a mock tool component."""
    return MockTool("test_tool")


@pytest.fixture
def mock_output():
    """Create a mock output component."""
    return MockOutput("test_output")


@pytest.fixture
def test_components():
    """Create a set of test components."""
    return create_test_components()


# Message Bus Fixtures
@pytest.fixture
def mock_message_bus():
    """Create a mock message bus."""
    return MockMessageBus()


@pytest.fixture
def mock_router():
    """Create a mock declarative router."""
    return create_mock_router()


@pytest.fixture
def real_message_bus():
    """Create a real InMemoryMessageBus for integration tests."""
    try:
        from woodwork.core.message_bus.in_memory_bus import InMemoryMessageBus
        bus = InMemoryMessageBus()
        bus.start()
        yield bus
        bus.stop()
    except ImportError:
        yield MockMessageBus()


@pytest.fixture
def real_router(real_message_bus):
    """Create a real DeclarativeRouter for integration tests."""
    try:
        from woodwork.core.message_bus.declarative_router import DeclarativeRouter
        return DeclarativeRouter(real_message_bus)
    except ImportError:
        return create_mock_router(real_message_bus)


# Message Fixtures
@pytest.fixture
def test_message():
    """Create a test message envelope."""
    return create_component_message(
        source="test_source",
        target="test_target",
        data={"action": "test", "inputs": {}}
    )


@pytest.fixture
def response_message():
    """Create a test response message."""
    return create_response_message(
        source="test_tool",
        target="test_agent",
        result="test_result",
        request_id="test_request_123"
    )


@pytest.fixture
def hook_message():
    """Create a test hook message."""
    return create_hook_message(
        event_type="agent.thought",
        data={"thought": "test thought"},
        source="test_agent"
    )


# Streaming Fixtures
@pytest.fixture
def mock_stream():
    """Create a mock stream."""
    return MockStream("test_stream_123")


@pytest.fixture
def mock_stream_manager():
    """Create a mock stream manager."""
    manager = Mock()
    manager.create_stream = AsyncMock(return_value="test_stream_123")
    manager.write_to_stream = AsyncMock(return_value=True)
    manager.close_stream = AsyncMock(return_value=True)

    # Mock async generator for reading
    async def mock_read():
        for i in range(3):
            yield f"chunk_{i}"

    manager.receive_stream.return_value = mock_read()
    return manager


@pytest.fixture
def streaming_component():
    """Create a component with streaming capabilities."""
    try:
        from woodwork.components.streaming_mixin import StreamingMixin

        class TestStreamingComponent(StreamingMixin):
            def __init__(self):
                super().__init__(name="test_streaming_component", config={})

        return TestStreamingComponent()
    except ImportError:
        # Return mock if streaming mixin not available
        return MockComponent("test_streaming_component", "streaming")


# Event System Fixtures
@pytest.fixture
def mock_event_manager():
    """Create a mock event manager."""
    return MockEventManager()


@pytest.fixture
def mock_payload():
    """Create a mock event payload."""
    return MockPayload({"test": "data", "timestamp": 1000.0})


@pytest.fixture
def test_event_data():
    """Create test event data."""
    return create_test_event_data()


@pytest.fixture
def mock_hooks():
    """Create mock hook functions."""
    return create_mock_hooks()


@pytest.fixture
def mock_pipes():
    """Create mock pipe functions."""
    return create_mock_pipes()


@pytest.fixture
def real_event_manager():
    """Create a real event manager if available."""
    try:
        from woodwork.events import create_default_emitter
        return create_default_emitter()
    except ImportError:
        return MockEventManager()


# Integration Test Fixtures
@pytest.fixture
async def full_system():
    """Create a complete system setup for integration tests."""
    try:
        from woodwork.core.message_bus.in_memory_bus import InMemoryMessageBus
        from woodwork.core.message_bus.declarative_router import DeclarativeRouter

        # Create message bus infrastructure
        message_bus = InMemoryMessageBus()
        message_bus.start()

        router = DeclarativeRouter(message_bus)

        # Create components
        components = create_test_components()

        # Configure routing
        component_configs = {
            name: {"object": component, "component": component.component}
            for name, component in components.items()
        }
        router.configure_from_components(component_configs)

        yield {
            "message_bus": message_bus,
            "router": router,
            "components": components,
            "event_manager": MockEventManager()
        }

        # Cleanup
        message_bus.stop()
    except ImportError:
        # Return mock system if real components not available
        yield {
            "message_bus": MockMessageBus(),
            "router": create_mock_router(),
            "components": create_test_components(),
            "event_manager": MockEventManager()
        }


# Performance Test Fixtures
@pytest.fixture
def performance_components():
    """Create components for performance testing."""
    components = {}
    for i in range(100):
        components[f"perf_component_{i}"] = MockComponent(f"perf_component_{i}", "test")
    return components


@pytest.fixture
def benchmark_data():
    """Create data for benchmarking tests."""
    return {
        "small_payload": {"size": "small", "data": "x" * 100},
        "medium_payload": {"size": "medium", "data": "x" * 10000},
        "large_payload": {"size": "large", "data": "x" * 1000000}
    }


# Utility Fixtures
@pytest.fixture
def capture_logs():
    """Capture log messages during test execution."""
    import logging
    from io import StringIO

    log_capture = StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.DEBUG)

    # Add to root logger
    root_logger = logging.getLogger()
    original_level = root_logger.level
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(handler)

    yield log_capture

    # Cleanup
    root_logger.removeHandler(handler)
    root_logger.setLevel(original_level)


@pytest.fixture
def temp_config_file(tmp_path):
    """Create a temporary configuration file for tests."""
    config_content = """
    # Test configuration
    test_component = test_type {
        name = "test_component"
        param1 = "value1"
        param2 = 42
    }
    """

    config_file = tmp_path / "test_config.ww"
    config_file.write_text(config_content)
    return str(config_file)


# Async Test Utilities
@pytest.fixture
def async_test_timeout():
    """Provide timeout for async tests."""
    return 5.0  # 5 seconds


# Test Markers
def pytest_configure(config):
    """Configure custom test markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as performance test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


# Test Collection Configuration
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on location."""
    for item in items:
        # Add markers based on test file location
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)

        # Mark async tests
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)


# Cleanup Fixtures
@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Cleanup resources after each test."""
    yield

    # Clear any global state
    # This is where you'd clean up singletons, global caches, etc.
    pass


# Test Data Factories
@pytest.fixture
def message_factory():
    """Factory for creating test messages."""
    def _create_message(source="default_source", target="default_target", **kwargs):
        return create_component_message(source=source, target=target, **kwargs)

    return _create_message


@pytest.fixture
def component_factory():
    """Factory for creating test components."""
    def _create_component(name="default_component", component_type="test", **kwargs):
        return MockComponent(name, component_type, **kwargs)

    return _create_component


# Error Simulation Fixtures
@pytest.fixture
def error_conditions():
    """Provide various error conditions for testing."""
    return {
        "network_error": ConnectionError("Network unreachable"),
        "timeout_error": TimeoutError("Operation timed out"),
        "invalid_data": ValueError("Invalid data format"),
        "permission_error": PermissionError("Access denied"),
        "resource_error": OSError("Resource not available")
    }


# Mock Patching Helpers
@pytest.fixture
def patch_time():
    """Patch time-related functions for deterministic tests."""
    with patch('time.time', return_value=1000.0), \
         patch('time.sleep'), \
         patch('asyncio.sleep', new_callable=AsyncMock):
        yield


@pytest.fixture
def patch_uuid():
    """Patch UUID generation for deterministic tests."""
    with patch('uuid.uuid4') as mock_uuid:
        mock_uuid.return_value.hex = "deterministic_uuid_1234"
        yield mock_uuid


# Database/Storage Mocks (if needed)
@pytest.fixture
def mock_storage():
    """Mock storage backend for tests."""
    storage = Mock()
    storage.read = AsyncMock(return_value={"data": "test"})
    storage.write = AsyncMock(return_value=True)
    storage.delete = AsyncMock(return_value=True)
    storage.exists = AsyncMock(return_value=True)
    return storage