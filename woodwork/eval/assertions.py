"""Deterministic assertion helpers for eval traces."""

from dataclasses import dataclass

from woodwork.eval.trace import Trace


@dataclass
class AssertionResult:
    """Result of a single assertion check."""

    name: str
    passed: bool
    message: str


def assert_tool_called(trace: Trace, tool_name: str) -> AssertionResult:
    """Assert that a specific tool was called during the trace."""
    called_tools = [e.data.get("tool", "") for e in trace.events if e.event_type == "tool.call"]
    if tool_name in called_tools:
        return AssertionResult(name=f"tool_called: {tool_name}", passed=True, message=f"tool '{tool_name}' was called")
    return AssertionResult(
        name=f"tool_called: {tool_name}",
        passed=False,
        message=f"expected tool '{tool_name}' to be called, got: {called_tools}",
    )


def assert_no_tools_called(trace: Trace) -> AssertionResult:
    """Assert that no tools were called during the trace."""
    called_tools = [e.data.get("tool", "") for e in trace.events if e.event_type == "tool.call"]
    if not called_tools:
        return AssertionResult(name="no_tools_called", passed=True, message="no tools were called")
    return AssertionResult(
        name="no_tools_called",
        passed=False,
        message=f"expected no tool calls, got: {called_tools}",
    )


def assert_response_contains(trace: Trace, substrings: list[str]) -> AssertionResult:
    """Assert that the response contains at least one of the given substrings (case-insensitive)."""
    response_lower = trace.response.lower()
    matched = [s for s in substrings if s.lower() in response_lower]
    if matched:
        return AssertionResult(
            name="response_contains",
            passed=True,
            message=f"response contains: {matched}",
        )
    return AssertionResult(
        name="response_contains",
        passed=False,
        message=f"response does not contain any of {substrings}",
    )


def assert_response_not_contains(trace: Trace, substrings: list[str]) -> AssertionResult:
    """Assert that the response does not contain any of the given substrings (case-insensitive)."""
    response_lower = trace.response.lower()
    found = [s for s in substrings if s.lower() in response_lower]
    if not found:
        return AssertionResult(
            name="response_not_contains",
            passed=True,
            message=f"response does not contain any of {substrings}",
        )
    return AssertionResult(
        name="response_not_contains",
        passed=False,
        message=f"response unexpectedly contains: {found}",
    )


def assert_max_steps(trace: Trace, max_steps: int) -> AssertionResult:
    """Assert that the agent completed within the given number of steps."""
    step_events = [e for e in trace.events if e.event_type == "agent.step_complete"]
    actual_steps = len(step_events)
    if actual_steps <= max_steps:
        return AssertionResult(
            name=f"max_steps: {max_steps}",
            passed=True,
            message=f"completed in {actual_steps} steps (max {max_steps})",
        )
    return AssertionResult(
        name=f"max_steps: {max_steps}",
        passed=False,
        message=f"took {actual_steps} steps, expected at most {max_steps}",
    )


def assert_min_tool_calls(trace: Trace, min_calls: int) -> AssertionResult:
    """Assert that the agent made at least the given number of tool calls."""
    tool_events = [e for e in trace.events if e.event_type == "tool.call"]
    actual = len(tool_events)
    if actual >= min_calls:
        return AssertionResult(
            name=f"min_tool_calls: {min_calls}",
            passed=True,
            message=f"made {actual} tool calls (min {min_calls})",
        )
    return AssertionResult(
        name=f"min_tool_calls: {min_calls}",
        passed=False,
        message=f"only made {actual} tool calls, expected at least {min_calls}",
    )


def evaluate_assertions(trace: Trace, assertions: dict) -> list[AssertionResult]:
    """Dispatch assertion dict to the appropriate assertion functions.

    Supported keys:
        tool_called: str
        no_tools_called: bool
        response_contains: list[str]
        response_not_contains: list[str]
        max_steps: int
        min_tool_calls: int
    """
    results: list[AssertionResult] = []

    if "tool_called" in assertions:
        results.append(assert_tool_called(trace, assertions["tool_called"]))

    if assertions.get("no_tools_called"):
        results.append(assert_no_tools_called(trace))

    if "response_contains" in assertions:
        results.append(assert_response_contains(trace, assertions["response_contains"]))

    if "response_not_contains" in assertions:
        results.append(assert_response_not_contains(trace, assertions["response_not_contains"]))

    if "max_steps" in assertions:
        results.append(assert_max_steps(trace, assertions["max_steps"]))

    if "min_tool_calls" in assertions:
        results.append(assert_min_tool_calls(trace, assertions["min_tool_calls"]))

    return results
