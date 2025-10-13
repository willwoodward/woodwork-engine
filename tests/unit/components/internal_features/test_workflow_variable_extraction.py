"""Tests for workflow variable extraction feature."""

import pytest
from unittest.mock import Mock
from woodwork.components.internal_features.workflow_variable_extraction import extract_variables_from_prompt


class MockLLM:
    """Mock LLM that returns variable extraction results."""
    def invoke(self, prompt):
        response = Mock()
        # Extract the user prompt from the extraction prompt
        # The user prompt is in quotes after "User prompt: "
        import re
        match = re.search(r'User prompt: "(.*?)"(?:\n|$)', prompt, re.DOTALL)
        if match:
            user_prompt = match.group(1)
        else:
            user_prompt = prompt

        # Determine what to extract based on the user prompt
        # Check more specific patterns first
        if "Alice" in user_prompt and "Bob" in user_prompt:
            # Multiple names
            response.content = '''```json
{
  "parameterized": "send email from {sender} to {recipient}",
  "variables": {"sender": "Alice", "recipient": "Bob"},
  "schema": {"sender": "string", "recipient": "string"}
}
```'''
        elif "Bob" in user_prompt and "5 days" in user_prompt:
            # Complex prompt
            response.content = '''```json
{
  "parameterized": "read all emails from {name} sent in the last {days} days",
  "variables": {"name": "Bob", "days": "5"},
  "schema": {"name": "string", "days": "number"}
}
```'''
        elif "Bob" in user_prompt:
            # Simple name extraction
            response.content = '''```json
{
  "parameterized": "read all emails from {name}",
  "variables": {"name": "Bob"},
  "schema": {"name": "string"}
}
```'''
        elif "10 emails" in user_prompt:
            # Count extraction
            response.content = '''```json
{
  "parameterized": "read {count} emails",
  "variables": {"count": "10"},
  "schema": {"count": "number"}
}
```'''
        elif "machine learning" in user_prompt:
            # Quoted string
            response.content = '''```json
{
  "parameterized": "search for {query} in documents",
  "variables": {"query": "machine learning"},
  "schema": {"query": "string"}
}
```'''
        elif "7 days" in user_prompt:
            # 7 days extraction
            response.content = '''```json
{
  "parameterized": "get the last {days} days of data",
  "variables": {"days": "7"},
  "schema": {"days": "number"}
}
```'''
        elif "5 days" in user_prompt:
            # 5 days extraction
            response.content = '''```json
{
  "parameterized": "get emails from the last {days} days",
  "variables": {"days": "5"},
  "schema": {"days": "number"}
}
```'''
        else:
            # No variables
            response.content = '''```json
{
  "parameterized": "list all files",
  "variables": {},
  "schema": {}
}
```'''
        return response


@pytest.fixture
def mock_llm():
    return MockLLM()


def test_extract_name_variable(mock_llm):
    """Test extracting person names from prompts."""
    prompt = "read all emails from Bob"
    parameterized, variables, schema = extract_variables_from_prompt(prompt, llm=mock_llm)

    assert "Bob" not in parameterized
    assert "{name}" in parameterized
    assert variables.get("name") == "Bob"
    assert schema.get("name") == "string"


def test_extract_multiple_names(mock_llm):
    """Test extracting multiple names."""
    prompt = "send email from Alice to Bob"
    parameterized, variables, schema = extract_variables_from_prompt(prompt, llm=mock_llm)

    assert "Alice" not in parameterized
    assert "Bob" not in parameterized
    assert len(variables) == 2
    assert "sender" in variables and "recipient" in variables


def test_extract_days_variable(mock_llm):
    """Test extracting time period."""
    prompt = "get emails from the last 5 days"
    parameterized, variables, schema = extract_variables_from_prompt(prompt, llm=mock_llm)

    assert "5" not in parameterized.split("{")[0]  # 5 should be in placeholder
    assert "{days}" in parameterized
    assert variables.get("days") == "5"
    assert schema.get("days") == "number"


def test_extract_count_variable(mock_llm):
    """Test extracting counts."""
    prompt = "read 10 emails"
    parameterized, variables, schema = extract_variables_from_prompt(prompt, llm=mock_llm)

    assert "{count}" in parameterized
    assert variables.get("count") == "10"
    assert schema.get("count") == "number"


def test_extract_quoted_string(mock_llm):
    """Test extracting quoted text."""
    prompt = 'search for "machine learning" in documents'
    parameterized, variables, schema = extract_variables_from_prompt(prompt, llm=mock_llm)

    assert "{query}" in parameterized
    assert variables.get("query") == "machine learning"
    assert schema.get("query") == "string"


def test_complex_prompt(mock_llm):
    """Test extracting multiple variable types from complex prompt."""
    prompt = "read all emails from Bob sent in the last 5 days"
    parameterized, variables, schema = extract_variables_from_prompt(prompt, llm=mock_llm)

    # Should extract both name and days
    assert len(variables) >= 2
    assert "name" in variables or any("name" in k for k in variables)
    assert "days" in variables or any("days" in k for k in variables)


def test_no_variables():
    """Test prompt with no extractable variables."""
    prompt = "list all files"
    parameterized, variables, schema = extract_variables_from_prompt(prompt)

    # Should return empty dicts if no variables found
    assert variables == {}
    assert schema == {}
    assert parameterized == prompt  # Unchanged


def test_preserve_plurals(mock_llm):
    """Test that plurals are preserved in parameterization."""
    prompt = "get the last 7 days of data"
    parameterized, variables, schema = extract_variables_from_prompt(prompt, llm=mock_llm)

    assert "days" in parameterized  # Plural should be preserved
    assert variables.get("days") == "7"


if __name__ == "__main__":
    # Run tests
    print("Testing variable extraction...")

    test_extract_name_variable()
    print("✓ Name extraction works")

    test_extract_days_variable()
    print("✓ Days extraction works")

    test_extract_count_variable()
    print("✓ Count extraction works")

    test_extract_quoted_string()
    print("✓ Quoted string extraction works")

    test_complex_prompt()
    print("✓ Complex prompt extraction works")

    test_no_variables()
    print("✓ No variables case works")

    print("\nAll tests passed!")
