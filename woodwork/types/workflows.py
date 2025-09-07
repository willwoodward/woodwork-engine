from dataclasses import dataclass
from typing import Any, List, Dict


@dataclass
class Action:
    tool: str
    action: str
    inputs: Dict[str, Any]
    output: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Action":
        return cls(tool=data["tool"], action=data["action"], inputs=data.get("inputs", {}), output=data["output"])

    def to_dict(self) -> Dict[str, Any]:
        return {"tool": self.tool, "action": self.action, "inputs": self.inputs, "output": self.output}


@dataclass
class Workflow:
    name: str
    inputs: Dict[str, Any]
    plan: List[Action]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Workflow":
        plan_data = data.get("plan", [])
        plan_actions = [Action.from_dict(action_dict) for action_dict in plan_data]
        return cls(name=data["name"], inputs=data.get("inputs", {}), plan=plan_actions)
