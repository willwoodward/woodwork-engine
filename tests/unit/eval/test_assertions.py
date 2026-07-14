"""Tests for eval assertion helpers."""

from woodwork.eval.assertions import (
    assert_max_steps,
    assert_min_tool_calls,
    assert_no_tools_called,
    assert_response_contains,
    assert_response_not_contains,
    assert_tool_called,
    evaluate_assertions,
)
from woodwork.eval.trace import Trace, TraceEvent


def _make_trace(events=None, response="test response"):
    return Trace(events=events or [], response=response, duration_seconds=1.0)


class TestAssertToolCalled:
    def test_pass_when_tool_called(self):
        trace = _make_trace(events=[TraceEvent("tool.call", 1.0, {"tool": "search"})])
        result = assert_tool_called(trace, "search")
        assert result.passed is True

    def test_fail_when_tool_not_called(self):
        trace = _make_trace(events=[TraceEvent("tool.call", 1.0, {"tool": "calendar"})])
        result = assert_tool_called(trace, "search")
        assert result.passed is False
        assert "search" in result.message

    def test_fail_when_no_tool_events(self):
        trace = _make_trace()
        result = assert_tool_called(trace, "search")
        assert result.passed is False


class TestAssertNoToolsCalled:
    def test_pass_when_no_tools(self):
        trace = _make_trace(events=[TraceEvent("agent.thought", 1.0, {"thought": "hello"})])
        result = assert_no_tools_called(trace)
        assert result.passed is True

    def test_fail_when_tools_called(self):
        trace = _make_trace(events=[TraceEvent("tool.call", 1.0, {"tool": "search"})])
        result = assert_no_tools_called(trace)
        assert result.passed is False
        assert "search" in result.message


class TestAssertResponseContains:
    def test_pass_when_contains(self):
        trace = _make_trace(response="Here are some high protein meals")
        result = assert_response_contains(trace, ["protein"])
        assert result.passed is True

    def test_pass_case_insensitive(self):
        trace = _make_trace(response="PROTEIN is important")
        result = assert_response_contains(trace, ["protein"])
        assert result.passed is True

    def test_pass_when_any_match(self):
        trace = _make_trace(response="Hello there!")
        result = assert_response_contains(trace, ["hi", "hello", "hey"])
        assert result.passed is True

    def test_fail_when_none_match(self):
        trace = _make_trace(response="Goodbye")
        result = assert_response_contains(trace, ["hello", "hi"])
        assert result.passed is False


class TestAssertResponseNotContains:
    def test_pass_when_not_contains(self):
        trace = _make_trace(response="Hello there")
        result = assert_response_not_contains(trace, ["error", "fail"])
        assert result.passed is True

    def test_fail_when_contains(self):
        trace = _make_trace(response="An error occurred")
        result = assert_response_not_contains(trace, ["error"])
        assert result.passed is False


class TestAssertMaxSteps:
    def test_pass_within_limit(self):
        events = [TraceEvent("agent.step_complete", float(i), {"step": i}) for i in range(3)]
        trace = _make_trace(events=events)
        result = assert_max_steps(trace, 5)
        assert result.passed is True

    def test_pass_at_limit(self):
        events = [TraceEvent("agent.step_complete", float(i), {"step": i}) for i in range(5)]
        trace = _make_trace(events=events)
        result = assert_max_steps(trace, 5)
        assert result.passed is True

    def test_fail_over_limit(self):
        events = [TraceEvent("agent.step_complete", float(i), {"step": i}) for i in range(6)]
        trace = _make_trace(events=events)
        result = assert_max_steps(trace, 5)
        assert result.passed is False


class TestAssertMinToolCalls:
    def test_pass_when_enough_calls(self):
        events = [TraceEvent("tool.call", float(i), {"tool": "search"}) for i in range(5)]
        trace = _make_trace(events=events)
        result = assert_min_tool_calls(trace, 3)
        assert result.passed is True

    def test_pass_at_exact_min(self):
        events = [TraceEvent("tool.call", float(i), {"tool": "search"}) for i in range(3)]
        trace = _make_trace(events=events)
        result = assert_min_tool_calls(trace, 3)
        assert result.passed is True

    def test_fail_when_too_few(self):
        events = [TraceEvent("tool.call", 1.0, {"tool": "search"})]
        trace = _make_trace(events=events)
        result = assert_min_tool_calls(trace, 5)
        assert result.passed is False
        assert "only made 1" in result.message


class TestEvaluateAssertions:
    def test_dispatches_tool_called(self):
        trace = _make_trace(events=[TraceEvent("tool.call", 1.0, {"tool": "search"})])
        results = evaluate_assertions(trace, {"tool_called": "search"})
        assert len(results) == 1
        assert results[0].passed is True

    def test_dispatches_multiple(self):
        trace = _make_trace(
            events=[TraceEvent("tool.call", 1.0, {"tool": "search"})],
            response="Here is some protein info",
        )
        results = evaluate_assertions(trace, {"tool_called": "search", "response_contains": ["protein"]})
        assert len(results) == 2
        assert all(r.passed for r in results)

    def test_empty_assertions(self):
        trace = _make_trace()
        results = evaluate_assertions(trace, {})
        assert results == []

    def test_no_tools_called_assertion(self):
        trace = _make_trace(events=[TraceEvent("agent.thought", 1.0, {"thought": "hi"})])
        results = evaluate_assertions(trace, {"no_tools_called": True})
        assert len(results) == 1
        assert results[0].passed is True
