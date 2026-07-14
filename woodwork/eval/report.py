"""Format eval results for console and JSON output."""

import json
from dataclasses import dataclass

from woodwork.eval.assertions import AssertionResult
from woodwork.eval.loader import EvalCase
from woodwork.eval.trace import Trace


@dataclass
class CaseResult:
    """Result of running a single eval case."""

    case: EvalCase
    trace: Trace
    assertions: list[AssertionResult]

    @property
    def passed(self) -> bool:
        return all(a.passed for a in self.assertions)


@dataclass
class EvalReport:
    """Aggregate report for an eval suite."""

    results: list[CaseResult]

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    def print_report(self) -> None:
        """Print a human-readable report to the console."""
        total = len(self.results)
        print(f"\nEVAL ({total} cases)")
        print("\u2501" * 40)

        for result in self.results:
            status = "\u2713" if result.passed else "\u2717"
            print(f"\n{status} {result.case.name} ({result.trace.duration_seconds:.1f}s)")

            # Print trace summary
            for event in result.trace.events:
                if event.event_type == "agent.thought":
                    thought = event.data.get("thought", "")
                    if thought:
                        print(f"  [thought] {thought[:120]}")
                elif event.event_type == "tool.call":
                    tool = event.data.get("tool", "unknown")
                    args = event.data.get("args", {})
                    print(f"  [tool] {tool} \u2192 {tool}({_format_args(args)})")
                elif event.event_type == "tool.observation":
                    tool = event.data.get("tool", "unknown")
                    obs = event.data.get("observation", "")
                    print(f"  [observation] {tool} \u2192 {obs[:80]!r}")
                elif event.event_type == "agent.error":
                    error = event.data.get("error", "")
                    print(f"  [error] {error[:120]}")

            # Print response
            response_preview = result.trace.response[:120] if result.trace.response else "(empty)"
            print(f"  Response: {response_preview!r}")

            # Print assertion results
            for a in result.assertions:
                a_status = "\u2713" if a.passed else "\u2717"
                print(f"  {a_status} {a.name}")
                if not a.passed:
                    print(f"    {a.message}")

        print("\n" + "\u2501" * 40)
        print(f"Results: {self.passed}/{total} passed")

    def to_dict(self) -> dict:
        """Convert report to a JSON-serializable dict."""
        return {
            "passed": self.passed,
            "failed": self.failed,
            "total": len(self.results),
            "cases": [
                {
                    "name": r.case.name,
                    "input": r.case.input,
                    "passed": r.passed,
                    "duration_seconds": r.trace.duration_seconds,
                    "response": r.trace.response,
                    "trace": [
                        {"event_type": e.event_type, "timestamp": e.timestamp, "data": e.data} for e in r.trace.events
                    ],
                    "assertions": [{"name": a.name, "passed": a.passed, "message": a.message} for a in r.assertions],
                }
                for r in self.results
            ],
        }


def _format_args(args: dict) -> str:
    """Format tool args as a compact string."""
    if not args:
        return ""
    parts = []
    for k, v in args.items():
        if isinstance(v, str) and len(v) > 40:
            v = v[:40] + "..."
        parts.append(f"{k}={json.dumps(v)}")
    return ", ".join(parts)
