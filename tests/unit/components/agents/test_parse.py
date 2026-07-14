"""Tests for agent_loop._parse and _extract_json_object."""

import pytest

from woodwork.components.agents.agent_loop import _extract_json_object, _parse


class TestExtractJsonObject:
    def test_simple_object(self):
        assert _extract_json_object('{"key": "value"}') == '{"key": "value"}'

    def test_nested_object(self):
        s = '{"tool": "search", "inputs": {"query": "hello"}, "output": "result"}'
        assert _extract_json_object(s) == s

    def test_double_nested(self):
        s = '{"a": {"b": {"c": 1}}, "d": 2}'
        assert _extract_json_object(s) == s

    def test_trailing_brace(self):
        """The edge case from gpt-5.4-nano: extra closing brace after valid JSON."""
        s = '{"tool":"search","inputs":{"query":"test"},"output":"r"}}'
        result = _extract_json_object(s)
        assert result == '{"tool":"search","inputs":{"query":"test"},"output":"r"}'

    def test_braces_in_strings(self):
        s = '{"key": "value with {braces} inside"}'
        assert _extract_json_object(s) == s

    def test_escaped_quotes(self):
        s = '{"key": "value with \\"escaped\\" quotes"}'
        assert _extract_json_object(s) == s

    def test_no_braces(self):
        assert _extract_json_object("no json here") == "no json here"

    def test_leading_text(self):
        s = 'some prefix {"key": "value"} trailing'
        assert _extract_json_object(s) == '{"key": "value"}'


class TestParse:
    def test_final_answer(self):
        thought, action, is_final = _parse("Final Answer: hello world")
        assert is_final is True
        assert thought == "hello world"
        assert action is None

    def test_thought_and_action(self):
        output = 'Thought: I should search\nAction: {"tool": "search", "action": "search", "inputs": {"query": "test"}, "output": "r"}'
        thought, action, is_final = _parse(output)
        assert is_final is False
        assert thought == "I should search"
        assert action["tool"] == "search"
        assert action["inputs"]["query"] == "test"

    def test_nested_json_action(self):
        """The exact pattern that caused 'Extra data' errors."""
        output = 'Thought: searching\nAction: {"tool":"search","action":"search","inputs":{"query":"site:heart.org AHA","max_results":5,"region":"us-en"},"output":"search_results2"}'
        thought, action, is_final = _parse(output)
        assert is_final is False
        assert action["tool"] == "search"
        assert action["inputs"]["query"] == "site:heart.org AHA"
        assert action["output"] == "search_results2"

    def test_trailing_braces(self):
        """Extra closing brace shouldn't break parsing."""
        output = 'Thought: go\nAction: {"tool":"search","action":"search","inputs":{"query":"test"},"output":"r"}}\n'
        thought, action, is_final = _parse(output)
        assert is_final is False
        assert action["tool"] == "search"

    def test_thought_only(self):
        thought, action, is_final = _parse("Thought: just thinking")
        assert is_final is False
        assert thought == "just thinking"
        assert action is None
