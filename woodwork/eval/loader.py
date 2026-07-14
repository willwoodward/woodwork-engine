"""Load YAML eval suites into structured data."""

import os
from dataclasses import dataclass

import yaml


@dataclass
class EvalCase:
    """A single eval case with input and assertions."""

    name: str
    input: str
    assertions: dict


@dataclass
class EvalSuite:
    """An eval suite: a .ww config path and list of cases."""

    config_path: str  # absolute path to the .ww file
    cases: list[EvalCase]


def load_suite(yaml_path: str) -> EvalSuite:
    """Load an eval suite from a YAML file.

    Expected format:
        config: main.ww
        cases:
          - name: case_name
            input: "user query"
            assert:
              tool_called: search
              response_contains: ["keyword"]
    """
    yaml_path = os.path.abspath(yaml_path)

    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Expected a YAML mapping at top level in {yaml_path}")

    config_rel = data.get("config")
    if not config_rel:
        raise ValueError(f"Missing 'config' key in {yaml_path}")

    # Resolve config path relative to the YAML file's directory
    yaml_dir = os.path.dirname(yaml_path)
    config_path = os.path.normpath(os.path.join(yaml_dir, config_rel))

    raw_cases = data.get("cases", [])
    if not raw_cases:
        raise ValueError(f"No cases defined in {yaml_path}")

    cases = []
    for i, raw in enumerate(raw_cases):
        name = raw.get("name")
        if not name:
            raise ValueError(f"Case {i} missing 'name' in {yaml_path}")

        case_input = raw.get("input")
        if not case_input:
            raise ValueError(f"Case '{name}' missing 'input' in {yaml_path}")

        assertions = raw.get("assert", {})

        cases.append(EvalCase(name=name, input=case_input, assertions=assertions))

    return EvalSuite(config_path=config_path, cases=cases)
