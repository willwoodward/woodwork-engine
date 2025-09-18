"""Event system fixtures for testing."""

from typing import Dict, Any, List
from unittest.mock import Mock
from woodwork.types.events import BasePayload


class MockPayload(BasePayload):
    """Mock event payload for testing."""

    def __init__(self, data: Dict[str, Any] = None, **kwargs):
        super().__init__(**kwargs)
        self.data = data

    def to_json(self) -> str:
        """Convert to JSON string."""
        import json
        return json.dumps(self.data)

    @classmethod
    def from_json(cls, json_str: str) -> 'MockPayload':
        """Create from JSON string."""
        import json
        data = json.loads(json_str)
        return cls(data)

    def validate(self) -> List[str]:
        """Validate payload."""
        return []


class MockEventManager:
    """Mock event manager for testing."""

    def __init__(self):
        self.emitted_events = []
        self.hooks = {}
        self.pipes = {}

    def emit(self, event_type: str, payload: Any):
        """Mock emit."""
        self.emitted_events.append((event_type, payload))

    def add_hook(self, event_type: str, hook_func):
        """Add hook."""
        if event_type not in self.hooks:
            self.hooks[event_type] = []
        self.hooks[event_type].append(hook_func)

    def add_pipe(self, event_type: str, pipe_func):
        """Add pipe."""
        if event_type not in self.pipes:
            self.pipes[event_type] = []
        self.pipes[event_type].append(pipe_func)


def create_test_event_data() -> Dict[str, Any]:
    """Create test event data."""
    return {
        "agent.thought": {"thought": "I need to analyze this problem"},
        "agent.action": {"tool": "planning_tools", "action": "write_todos", "inputs": {}},
        "tool.call": {"tool_name": "github_api", "arguments": {"repo": "test"}},
        "tool.observation": {"result": "GitHub API call successful"},
        "input.received": {"input": "Please help me with this task", "session_id": "test"},
        "agent.step_complete": {"step_number": 1, "status": "completed"}
    }


def create_mock_hooks() -> Dict[str, callable]:
    """Create mock hook functions."""
    return {
        "debug_hook": Mock(return_value=None),
        "logging_hook": Mock(return_value=None),
        "metrics_hook": Mock(return_value=None)
    }


def create_mock_pipes() -> Dict[str, callable]:
    """Create mock pipe functions."""
    return {
        "input_transformer": Mock(side_effect=lambda x: x),
        "output_formatter": Mock(side_effect=lambda x: x),
        "error_handler": Mock(side_effect=lambda x: x)
    }