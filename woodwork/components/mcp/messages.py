"""
MCP Message Types and Serialization

Handles JSON-RPC message format used by Model Context Protocol.
"""

import json
import uuid
from typing import Any, Dict, Optional, Union
from dataclasses import dataclass


@dataclass
class MCPMessage:
    """MCP JSON-RPC message representation."""

    id: Optional[str] = None
    method: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Validate message structure."""
        if self.id is None:
            self.id = str(uuid.uuid4())

    @property
    def is_request(self) -> bool:
        """Check if this is a request message."""
        return self.method is not None and self.result is None and self.error is None

    @property
    def is_response(self) -> bool:
        """Check if this is a response message."""
        return self.method is None and (self.result is not None or self.error is not None)

    @property
    def is_notification(self) -> bool:
        """Check if this is a notification (request without ID)."""
        return self.method is not None and self.id is None

    def to_json(self) -> str:
        """Serialize to JSON string."""
        data = {
            "jsonrpc": "2.0",
        }

        if self.id is not None:
            data["id"] = self.id

        if self.method is not None:
            data["method"] = self.method

        if self.params is not None:
            data["params"] = self.params

        if self.result is not None:
            data["result"] = self.result

        if self.error is not None:
            data["error"] = self.error

        return json.dumps(data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = {
            "jsonrpc": "2.0",
        }

        if self.id is not None:
            data["id"] = self.id

        if self.method is not None:
            data["method"] = self.method

        if self.params is not None:
            data["params"] = self.params

        if self.result is not None:
            data["result"] = self.result

        if self.error is not None:
            data["error"] = self.error

        return data

    @classmethod
    def from_json(cls, json_str: str) -> "MCPMessage":
        """Create message from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPMessage":
        """Create message from dictionary."""
        return cls(
            id=data.get("id"),
            method=data.get("method"),
            params=data.get("params"),
            result=data.get("result"),
            error=data.get("error")
        )


class MCPError(Exception):
    """MCP-specific error."""

    def __init__(self, error_data: Dict[str, Any]):
        self.code = error_data.get("code", -1)
        self.message = error_data.get("message", "Unknown error")
        self.data = error_data.get("data")
        super().__init__(self.message)