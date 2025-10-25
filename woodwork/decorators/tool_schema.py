"""
Tool schema decorator for attaching metadata to tool classes.

Allows tools to define their parameter schema declaratively for
workflow builder integration.
"""

from typing import List
from woodwork.types.tool_schema import ToolSchema, ToolParameter


def tool_schema(
    display_name: str,
    description: str,
    category: str,
    parameters: List[ToolParameter],
    output_type: str = "string"
):
    """
    Decorator to attach schema metadata to tool classes.

    Args:
        display_name: Human-readable tool name
        description: Tool description for UI
        category: Tool category (file, data, ml, api, agent, general)
        parameters: List of ToolParameter definitions
        output_type: Type of output variable (default: "string")

    Example:
        ```python
        from woodwork.decorators import tool_schema
        from woodwork.types.tool_schema import ToolParameter

        @tool_schema(
            display_name="File Reader",
            description="Read files from filesystem",
            category="file",
            parameters=[
                ToolParameter(
                    name="file_path",
                    type="string",
                    description="Path to file",
                    required=True
                ),
                ToolParameter(
                    name="format",
                    type="enum",
                    description="File format",
                    enum=["csv", "json", "xml"],
                    default="csv"
                )
            ],
            output_type="string"
        )
        class file_reader_tool(tool_interface):
            def __init__(self, name="file_reader", **config):
                super().__init__(name=name, **config)

            def input(self, action: str, inputs: dict):
                # Implementation
                pass
        ```
    """
    def decorator(cls):
        # Store schema as class attribute
        schema = ToolSchema(
            tool_name=cls.__name__,
            display_name=display_name,
            description=description,
            category=category,
            parameters=parameters,
            output_type=output_type
        )
        cls.__tool_schema__ = schema
        return cls
    return decorator
