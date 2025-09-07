from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class Prompt:
    file: str
    variables: Dict[str, Any]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Prompt":
        return cls(file=data["file"], variables=data.get("variables", {}))

    def to_dict(self) -> Dict[str, Any]:
        return {"file": self.file, "variables": self.variables}
