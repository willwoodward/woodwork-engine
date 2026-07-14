"""Control-flow directives returned by agent loop steps."""

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class Halt:
    """Stop the agent loop and return a final answer."""

    answer: str


@dataclass
class Retry:
    """Retry the current step (e.g. after a transient tool error)."""

    reason: str
    max_retries: int = 3


@dataclass
class Spawn:
    """Spawn a sub-agent to handle part of the task."""

    agent_name: str
    query: str
    inputs: Dict[str, Any] = field(default_factory=dict)
