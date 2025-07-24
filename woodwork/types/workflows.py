from dataclasses import dataclass
from typing import Any

@dataclass
class Action:
    tool: str
    action: str
    inputs: dict[str, Any]
    output: str

@dataclass
class Workflow:
    name: str
    inputs: dict[str, Any]
    plan: list[Action]
