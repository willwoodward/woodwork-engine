"""
Tool schema types for workflow builder.

Defines metadata structures for tools to enable dynamic UI generation
and schema-driven workflow construction.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolParameter:
    """Parameter definition for a tool."""

    name: str
    type: str  # "string", "number", "boolean", "object", "array", "enum"
    description: str
    required: bool = False
    default: Any = None
    enum: Optional[List[str]] = None  # For dropdown options

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        result = {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "required": self.required,
        }
        if self.default is not None:
            result["default"] = self.default
        if self.enum is not None:
            result["enum"] = self.enum
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolParameter":
        """Deserialize from dict."""
        return cls(
            name=data["name"],
            type=data["type"],
            description=data["description"],
            required=data.get("required", False),
            default=data.get("default"),
            enum=data.get("enum"),
        )


@dataclass
class ToolSchema:
    """Complete schema definition for a tool."""

    tool_name: str
    display_name: str
    description: str
    category: str  # "file", "data", "ml", "api", "agent", "general"
    parameters: List[ToolParameter] = field(default_factory=list)
    output_type: str = "string"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "tool_name": self.tool_name,
            "display_name": self.display_name,
            "description": self.description,
            "category": self.category,
            "parameters": [p.to_dict() for p in self.parameters],
            "output_type": self.output_type,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolSchema":
        """Deserialize from dict."""
        parameters = [ToolParameter.from_dict(p) for p in data.get("parameters", [])]
        return cls(
            tool_name=data["tool_name"],
            display_name=data["display_name"],
            description=data["description"],
            category=data["category"],
            parameters=parameters,
            output_type=data.get("output_type", "string"),
        )
