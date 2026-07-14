"""Core data types for agent execution."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Message:
    """A single message in a conversation."""

    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class Step:
    """A single ReAct step: thought + optional action + observation."""

    thought: str
    tool: Optional[str] = None
    action: Optional[str] = None
    inputs: Dict[str, Any] = field(default_factory=dict)
    observation: Optional[str] = None
    output_var: Optional[str] = None


@dataclass
class AgentContext:
    """Context for a single agent invocation."""

    query: str
    session_id: str
    inputs: Dict[str, Any] = field(default_factory=dict)
    history: List[Message] = field(default_factory=list)
    steps: List[Step] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
