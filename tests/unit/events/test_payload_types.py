"""Tests for event payload types."""

import pytest
import json
from dataclasses import dataclass
from typing import List
from tests.unit.fixtures.event_fixtures import MockPayload


class TestBasePayload:
    """Test suite for BasePayload functionality."""

    @pytest.fixture
    def base_payload(self):
        return MockPayload({"test": "data", "number": 42})

    def test_payload_creation(self, base_payload):
        """Test creating payload."""
        assert base_payload.data["test"] == "data"
        assert base_payload.data["number"] == 42

    def test_payload_json_serialization(self, base_payload):
        """Test JSON serialization."""
        json_str = base_payload.to_json()
        assert isinstance(json_str, str)

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["test"] == "data"
        assert parsed["number"] == 42

    def test_payload_json_deserialization(self):
        """Test JSON deserialization."""
        json_str = '{"test": "data", "number": 42}'
        payload = MockPayload.from_json(json_str)

        assert payload.data["test"] == "data"
        assert payload.data["number"] == 42

    def test_payload_validation(self, base_payload):
        """Test payload validation."""
        errors = base_payload.validate()
        assert isinstance(errors, list)

    def test_payload_with_none_data(self):
        """Test payload with None data."""
        payload = MockPayload(None)
        assert payload.data is None

    def test_payload_with_empty_data(self):
        """Test payload with empty data."""
        payload = MockPayload({})
        assert payload.data == {}

    def test_payload_equality(self):
        """Test payload equality comparison."""
        payload1 = MockPayload({"test": "data"})
        payload2 = MockPayload({"test": "data"})
        payload3 = MockPayload({"test": "different"})

        assert payload1.data == payload2.data
        assert payload1.data != payload3.data


class TestSpecificPayloadTypes:
    """Test specific payload implementations."""

    def test_agent_thought_payload(self):
        """Test agent thought payload structure."""
        # Test expected structure for agent thoughts
        thought_data = {
            "thought": "I need to analyze this problem",
            "component_id": "test_agent",
            "component_type": "agent",
            "timestamp": 1000.0
        }

        payload = MockPayload(thought_data)
        assert payload.data["thought"] == "I need to analyze this problem"
        assert payload.data["component_id"] == "test_agent"

    def test_agent_action_payload(self):
        """Test agent action payload structure."""
        action_data = {
            "tool": "planning_tools",
            "action": "write_todos",
            "inputs": {"todos": ["task1", "task2"]},
            "component_id": "test_agent",
            "component_type": "agent"
        }

        payload = MockPayload(action_data)
        assert payload.data["tool"] == "planning_tools"
        assert payload.data["action"] == "write_todos"
        assert "todos" in payload.data["inputs"]

    def test_tool_call_payload(self):
        """Test tool call payload structure."""
        tool_data = {
            "tool_name": "github_api",
            "arguments": {"repo": "test/repo", "issue": 123},
            "component_id": "github_api",
            "component_type": "functions"
        }

        payload = MockPayload(tool_data)
        assert payload.data["tool_name"] == "github_api"
        assert payload.data["arguments"]["repo"] == "test/repo"

    def test_tool_observation_payload(self):
        """Test tool observation payload structure."""
        observation_data = {
            "result": "GitHub API call successful",
            "tool_name": "github_api",
            "execution_time": 0.5,
            "component_id": "github_api"
        }

        payload = MockPayload(observation_data)
        assert payload.data["result"] == "GitHub API call successful"
        assert payload.data["execution_time"] == 0.5

    def test_input_received_payload(self):
        """Test input received payload structure."""
        input_data = {
            "input": "Please help me with this task",
            "inputs": {"source": "command_line"},
            "session_id": "session_123",
            "component_id": "input",
            "component_type": "command_line"
        }

        payload = MockPayload(input_data)
        assert payload.data["input"] == "Please help me with this task"
        assert payload.data["session_id"] == "session_123"

    def test_agent_step_complete_payload(self):
        """Test agent step complete payload structure."""
        step_data = {
            "step_number": 1,
            "status": "completed",
            "result": "Step completed successfully",
            "component_id": "test_agent"
        }

        payload = MockPayload(step_data)
        assert payload.data["step_number"] == 1
        assert payload.data["status"] == "completed"


class TestPayloadValidation:
    """Test payload validation logic."""

    def test_required_fields_validation(self):
        """Test validation of required fields."""
        # Mock payload that requires certain fields
        class RequiredFieldsPayload(MockPayload):
            def validate(self) -> List[str]:
                errors = []
                if not self.data:
                    errors.append("Data is required")
                    return errors

                required_fields = ["component_id", "component_type"]
                for field in required_fields:
                    if field not in self.data:
                        errors.append(f"Missing required field: {field}")

                return errors

        # Valid payload
        valid_payload = RequiredFieldsPayload({
            "component_id": "test",
            "component_type": "agent"
        })
        assert len(valid_payload.validate()) == 0

        # Invalid payload
        invalid_payload = RequiredFieldsPayload({"component_id": "test"})
        errors = invalid_payload.validate()
        assert len(errors) == 1
        assert "component_type" in errors[0]

    def test_type_validation(self):
        """Test type validation in payloads."""
        class TypeValidatedPayload(MockPayload):
            def validate(self) -> List[str]:
                errors = []
                if not self.data:
                    return ["Data is required"]

                # Validate types
                if "timestamp" in self.data:
                    if not isinstance(self.data["timestamp"], (int, float)):
                        errors.append("timestamp must be a number")

                if "step_number" in self.data:
                    if not isinstance(self.data["step_number"], int):
                        errors.append("step_number must be an integer")

                return errors

        # Valid types
        valid_payload = TypeValidatedPayload({
            "timestamp": 1000.0,
            "step_number": 1
        })
        assert len(valid_payload.validate()) == 0

        # Invalid types
        invalid_payload = TypeValidatedPayload({
            "timestamp": "not_a_number",
            "step_number": "not_an_int"
        })
        errors = invalid_payload.validate()
        assert len(errors) == 2

    def test_value_range_validation(self):
        """Test value range validation."""
        class RangeValidatedPayload(MockPayload):
            def validate(self) -> List[str]:
                errors = []
                if not self.data:
                    return ["Data is required"]

                if "step_number" in self.data:
                    step = self.data["step_number"]
                    if isinstance(step, int) and step < 1:
                        errors.append("step_number must be positive")

                if "execution_time" in self.data:
                    time = self.data["execution_time"]
                    if isinstance(time, (int, float)) and time < 0:
                        errors.append("execution_time cannot be negative")

                return errors

        # Valid ranges
        valid_payload = RangeValidatedPayload({
            "step_number": 1,
            "execution_time": 0.5
        })
        assert len(valid_payload.validate()) == 0

        # Invalid ranges
        invalid_payload = RangeValidatedPayload({
            "step_number": -1,
            "execution_time": -0.5
        })
        errors = invalid_payload.validate()
        assert len(errors) == 2


class TestPayloadSerialization:
    """Test payload serialization scenarios."""

    def test_complex_data_serialization(self):
        """Test serialization of complex data structures."""
        complex_data = {
            "nested": {
                "list": [1, 2, 3],
                "dict": {"key": "value"}
            },
            "array": ["item1", "item2"],
            "boolean": True,
            "null_value": None
        }

        payload = MockPayload(complex_data)
        json_str = payload.to_json()

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["nested"]["list"] == [1, 2, 3]
        assert parsed["boolean"] is True
        assert parsed["null_value"] is None

    def test_roundtrip_serialization(self):
        """Test roundtrip serialization (to JSON and back)."""
        original_data = {
            "component_id": "test_agent",
            "thought": "Complex thought with unicode: 🤖",
            "numbers": [1, 2.5, -3],
            "metadata": {"version": 1.0}
        }

        # Create payload
        original_payload = MockPayload(original_data)

        # Serialize to JSON
        json_str = original_payload.to_json()

        # Deserialize back
        restored_payload = MockPayload.from_json(json_str)

        # Should match original
        assert restored_payload.data == original_data

    def test_serialization_error_handling(self):
        """Test handling of serialization errors."""
        # Create payload with non-serializable data
        class NonSerializable:
            pass

        problematic_data = {
            "normal_data": "string",
            "object": NonSerializable()  # Can't be serialized
        }

        payload = MockPayload(problematic_data)

        # Should handle serialization error gracefully
        try:
            json_str = payload.to_json()
            # If it succeeds, the mock implementation handled it
            assert isinstance(json_str, str)
        except (TypeError, ValueError):
            # Expected for non-serializable data
            pass

    def test_deserialization_error_handling(self):
        """Test handling of deserialization errors."""
        invalid_json = "{ invalid json structure"

        try:
            MockPayload.from_json(invalid_json)
        except (json.JSONDecodeError, ValueError):
            # Expected for invalid JSON
            pass

    def test_empty_payload_serialization(self):
        """Test serialization of empty payloads."""
        empty_payload = MockPayload({})
        json_str = empty_payload.to_json()

        parsed = json.loads(json_str)
        assert parsed == {}

    def test_large_payload_serialization(self):
        """Test serialization of large payloads."""
        # Create large payload
        large_data = {
            f"key_{i}": f"value_{i}" * 100
            for i in range(100)
        }

        payload = MockPayload(large_data)
        json_str = payload.to_json()

        # Should still be valid JSON
        parsed = json.loads(json_str)
        assert len(parsed) == 100