"""Mock components for testing the event-driven architecture."""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from unittest.mock import Mock, AsyncMock
import asyncio


@dataclass
class MockComponent:
    """Mock component that mimics real component behavior."""
    name: str
    type: str = "test"
    component: str = "test"
    _received_responses: Dict[str, Any] = field(default_factory=dict)
    _router: Optional[Any] = None

    def set_router(self, router):
        """Set router on component."""
        self._router = router

    def input(self, action: str, inputs: Dict[str, Any]) -> str:
        """Mock input method."""
        return f"mock_result_{action}_{self.name}"


@dataclass
class MockAgent(MockComponent):
    """Mock agent component with tool execution capabilities."""
    type: str = "agent"
    component: str = "llm"

    async def execute_tool(self, tool_name: str, action: str, inputs: Dict[str, Any]) -> str:
        """Mock tool execution."""
        return f"agent_{self.name}_executed_{tool_name}_{action}"


@dataclass
class MockTool(MockComponent):
    """Mock tool component."""
    type: str = "tool"
    component: str = "functions"

    def execute(self, action: str, **kwargs) -> str:
        """Mock tool execution."""
        return f"tool_{self.name}_result_{action}"


@dataclass
class MockOutput(MockComponent):
    """Mock output component."""
    type: str = "output"
    component: str = "console"

    def output(self, data: Any) -> None:
        """Mock output method."""
        pass


class MockMessageBus:
    """Mock message bus for testing."""

    def __init__(self):
        self.component_handlers = {}
        self.sent_messages = []
        self.published_messages = []

    def register_component_handler(self, component_id: str, handler):
        """Register component handler."""
        self.component_handlers[component_id] = handler

    async def send_to_component(self, envelope) -> bool:
        """Mock send to component."""
        self.sent_messages.append(envelope)

        # Try to deliver to registered handler
        handler = self.component_handlers.get(envelope.target_component)
        if handler:
            if asyncio.iscoroutinefunction(handler):
                await handler(envelope)
            else:
                handler(envelope)

        return True

    async def publish(self, envelope) -> bool:
        """Mock publish."""
        self.published_messages.append(envelope)
        return True


class MockStream:
    """Mock stream for testing streaming components."""

    def __init__(self, stream_id: str = "test_stream_123"):
        self.id = stream_id
        self.data = []
        self.closed = False

    async def write(self, data: Any):
        """Write data to stream."""
        if self.closed:
            raise RuntimeError("Stream is closed")
        self.data.append(data)

    async def close(self):
        """Close stream."""
        self.closed = True

    async def read(self):
        """Read from stream."""
        for item in self.data:
            yield item


def create_test_components() -> Dict[str, MockComponent]:
    """Create a set of test components."""
    return {
        'test_agent': MockAgent('test_agent'),
        'test_tool': MockTool('test_tool'),
        'test_output': MockOutput('test_output'),
        'planning_tools': MockTool('planning_tools', component='planning_tools'),
        'github_api': MockTool('github_api', component='functions'),
    }


def create_test_component_configs() -> Dict[str, Dict[str, Any]]:
    """Create a set of test component configurations for router testing."""
    return {
        'test_agent': {
            'variable': 'test_agent',
            'component': 'agent',
            'type': 'llm',
            'config': {},
            'to': ['test_tool']
        },
        'test_tool': {
            'variable': 'test_tool',
            'component': 'tool',
            'type': 'functions',
            'config': {},
            'to': ['test_output']
        },
        'test_output': {
            'variable': 'test_output',
            'component': 'output',
            'type': 'console',
            'config': {}
        },
        'planning_tools': {
            'variable': 'planning_tools',
            'component': 'tool',
            'type': 'planning_tools',
            'config': {}
        },
        'github_api': {
            'variable': 'github_api',
            'component': 'tool',
            'type': 'functions',
            'config': {}
        },
    }


def create_workflow_inference_configs() -> Dict[str, Dict[str, Any]]:
    """Create configs specifically for workflow inference testing."""
    return {
        "input": {"component": "command_line", "type": "cli"},
        "agent": {"component": "llms", "type": "openai"},
        "output": {"component": "console", "type": "cli"},
        "tool": {"component": "functions", "type": "api"}
    }


def create_mock_router(message_bus=None, time_source=None):
    """Create a mock router with configurable dependencies."""
    from unittest.mock import Mock

    router = Mock()
    router.message_bus = message_bus or MockMessageBus()
    router.time_source = time_source or (lambda: 1000.0)
    router.component_configs = {}
    router.routing_table = {}

    # Mock methods
    router.configure_from_components = Mock()
    router.send_to_component = AsyncMock(return_value=True)
    router.send_to_component_with_response = AsyncMock(return_value=(True, "test_request_id"))

    return router