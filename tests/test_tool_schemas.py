"""
Unit tests for tool schema system.
"""

import pytest
from woodwork.types.tool_schema import ToolParameter, ToolSchema
from woodwork.core.unified_event_bus import UnifiedEventBus


class MockTool:
    """Mock tool for testing."""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description

    def input(self, action: str, inputs: dict):
        return f"Mock result for {action}"


class MockAgent:
    """Mock agent with tools."""

    def __init__(self, name: str, tools: list):
        self.name = name
        self._tools = tools


def test_tool_parameter_serialization():
    """Test ToolParameter serialization."""
    param = ToolParameter(
        name="file_path", type="string", description="Path to file", required=True, default="/tmp/file.txt"
    )

    data = param.to_dict()
    assert data["name"] == "file_path"
    assert data["type"] == "string"
    assert data["required"] is True
    assert data["default"] == "/tmp/file.txt"

    # Test deserialization
    param2 = ToolParameter.from_dict(data)
    assert param2.name == param.name
    assert param2.type == param.type
    assert param2.required == param.required


def test_tool_parameter_enum():
    """Test ToolParameter with enum values."""
    param = ToolParameter(name="format", type="enum", description="File format", enum=["csv", "json", "xml"])

    data = param.to_dict()
    assert data["enum"] == ["csv", "json", "xml"]


def test_tool_schema_serialization():
    """Test ToolSchema serialization."""
    schema = ToolSchema(
        tool_name="file_reader",
        display_name="File Reader",
        description="Read files from filesystem",
        category="file",
        parameters=[ToolParameter(name="path", type="string", description="File path", required=True)],
        output_type="string",
    )

    data = schema.to_dict()
    assert data["tool_name"] == "file_reader"
    assert data["category"] == "file"
    assert len(data["parameters"]) == 1
    assert data["parameters"][0]["name"] == "path"

    # Test deserialization
    schema2 = ToolSchema.from_dict(data)
    assert schema2.tool_name == schema.tool_name
    assert len(schema2.parameters) == 1


def test_event_bus_register_tool_schema():
    """Test tool schema registration in event bus."""
    event_bus = UnifiedEventBus()

    schema = ToolSchema(
        tool_name="test_tool",
        display_name="Test Tool",
        description="Test",
        category="general",
        parameters=[],
        output_type="string",
    )

    event_bus.register_tool_schema(schema)
    assert event_bus.get_tool_schema("test_tool") == schema
    assert "test_tool" in [s.tool_name for s in event_bus.get_all_tool_schemas()]


def test_event_bus_discover_tools_from_agent():
    """Test automatic schema discovery from agent's tools."""
    event_bus = UnifiedEventBus()

    tool1 = MockTool("file_reader", "Reads files")
    tool2 = MockTool("data_processor", "Processes data")
    agent = MockAgent("test_agent", tools=[tool1, tool2])

    schemas = event_bus.discover_tools_from_agent(agent)

    assert len(schemas) == 2
    assert event_bus.get_tool_schema("file_reader") is not None
    assert event_bus.get_tool_schema("data_processor") is not None

    # Check inferred properties
    file_reader_schema = event_bus.get_tool_schema("file_reader")
    assert file_reader_schema.display_name == "File Reader"
    # Category is inferred from class name (MockTool), not tool name
    assert file_reader_schema.category == "general"


def test_event_bus_tool_category_inference():
    """Test tool category inference from class names."""
    event_bus = UnifiedEventBus()

    # Create mock classes with different names to test category inference
    class file_reader_tool:
        def __init__(self):
            self.name = "file_reader"
            self.description = "Reads files"

    class api_client_tool:
        def __init__(self):
            self.name = "api_client"
            self.description = "API client"

    class data_cleaner_tool:
        def __init__(self):
            self.name = "data_cleaner"
            self.description = "Cleans data"

    class ml_trainer_tool:
        def __init__(self):
            self.name = "ml_trainer"
            self.description = "Trains ML models"

    test_cases = [
        (file_reader_tool(), "file"),
        (api_client_tool(), "api"),
        (data_cleaner_tool(), "data"),
        (ml_trainer_tool(), "ml"),
    ]

    for tool, expected_category in test_cases:
        schema = event_bus._extract_schema_from_tool(tool)
        assert schema.category == expected_category, f"Failed for {tool.name}"


def test_event_bus_tool_with_decorator_schema():
    """Test tool with decorator-defined schema."""
    from woodwork.decorators import tool_schema

    @tool_schema(
        display_name="Custom Tool",
        description="Custom description",
        category="custom",
        parameters=[ToolParameter(name="param1", type="string", description="Test")],
        output_type="object",
    )
    class CustomTool:
        def __init__(self):
            self.name = "custom_tool"

    event_bus = UnifiedEventBus()
    tool = CustomTool()

    # Manually extract schema (decorator sets __tool_schema__)
    schema = event_bus._extract_schema_from_tool(tool)

    assert schema.display_name == "Custom Tool"
    assert schema.category == "custom"
    assert len(schema.parameters) == 1
    assert schema.output_type == "object"


def test_event_bus_tool_stats():
    """Test tool registration statistics."""
    event_bus = UnifiedEventBus()

    schema1 = ToolSchema(tool_name="tool1", display_name="Tool 1", description="Test", category="general")
    schema2 = ToolSchema(tool_name="tool2", display_name="Tool 2", description="Test", category="general")

    event_bus.register_tool_schema(schema1)
    event_bus.register_tool_schema(schema2)

    stats = event_bus.get_stats()
    assert stats["tools_registered"] == 2


def test_tool_schema_empty_parameters():
    """Test tool schema with no parameters."""
    schema = ToolSchema(
        tool_name="simple_tool", display_name="Simple Tool", description="No parameters", category="general"
    )

    data = schema.to_dict()
    assert data["parameters"] == []
    assert data["output_type"] == "string"  # Default


def test_tool_parameter_optional():
    """Test optional tool parameters."""
    param = ToolParameter(name="optional_param", type="string", description="Optional parameter", required=False)

    data = param.to_dict()
    assert data["required"] is False
    assert "default" not in data  # Should not include None defaults


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
