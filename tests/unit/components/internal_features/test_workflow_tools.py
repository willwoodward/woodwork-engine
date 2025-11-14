"""Tests for workflow tools functionality."""

import pytest
from unittest.mock import Mock
from woodwork.components.internal_features.workflows import WorkflowsFeature


class MockLLM:
    """Mock LLM for testing."""

    def invoke(self, prompt):
        response = Mock()
        response.content = """```json
{
  "parameterized": "summarise {name}'s messages",
  "variables": {"name": "Bob"},
  "schema": {"name": "string"}
}
```"""
        return response


class MockNeo4j:
    """Mock Neo4j component."""

    def __init__(self):
        self.workflows = {}

    def run(self, query, params):
        if "WHERE p.text CONTAINS" in query or "MATCH (w:Workflow {id:" in query:
            name = params.get("name", "")
            if "Email Summary" in name or name == "test-workflow-123":
                return [{"workflow_id": "test-workflow-123"}]
        return []

    def init_vector_index(self, *args, **kwargs):
        pass


class MockWorkflowExecutor:
    """Mock workflow executor."""

    async def execute_workflow(self, workflow_id, inputs, session_id):
        return {
            "status": "completed",
            "result": f"Executed {workflow_id}",
            "workflow_id": workflow_id,
            "inputs": inputs,
        }


@pytest.fixture
def workflows_feature():
    feature = WorkflowsFeature()
    feature._neo4j_component = MockNeo4j()
    feature._workflow_executor = MockWorkflowExecutor()
    feature._llm = MockLLM()
    feature._component_ref = Mock()
    feature._component_ref.name = "test_agent"
    feature._component_ref.session_id = "test-session"
    return feature


def test_get_workflow_id_by_name_exact(workflows_feature):
    """Test workflow lookup by exact ID."""
    wf_id = workflows_feature._get_workflow_id_by_name("test-workflow-123")
    assert wf_id == "test-workflow-123"


def test_get_workflow_id_by_name_text(workflows_feature):
    """Test workflow lookup by text match."""
    wf_id = workflows_feature._get_workflow_id_by_name("Email Summary")
    assert wf_id == "test-workflow-123"


def test_get_workflow_id_not_found(workflows_feature):
    """Test workflow lookup when not found."""
    wf_id = workflows_feature._get_workflow_id_by_name("Nonexistent")
    assert wf_id is None


@pytest.mark.asyncio
async def test_execute_workflow_tool(workflows_feature):
    """Test workflow execution."""
    result = await workflows_feature._execute_workflow_tool("test-workflow-123", {"name": "Alice"})
    assert result["status"] == "completed"
    assert result["inputs"]["name"] == "Alice"


def test_format_workflow_contexts(workflows_feature):
    """Test formatting workflow contexts."""
    contexts = [
        {
            "rank": 1,
            "similarity": 0.95,
            "workflow_id": "test-123",
            "name": "Email Summary",
            "parameterized_prompt": "summarise {name}'s messages",
            "input_variables": {"name": "Bob"},
            "actions": [{"tool": "email", "action": "get"}],
        }
    ]
    formatted = workflows_feature._format_workflow_contexts(contexts)
    assert "Email Summary" in formatted
    assert '"tool": "workflow"' in formatted


def test_get_tools_returns_cached_workflows(workflows_feature):
    """Test get_tools returns cached similar workflows as tools."""
    # Setup cached workflows
    workflows_feature._similar_workflows = [
        {
            "rank": 1,
            "similarity": 0.95,
            "workflow_id": "test-123",
            "name": "Email Summary",
            "parameterized_prompt": "summarise {name}'s messages",
            "input_variables": {"name": "Bob"},
            "actions": [{"tool": "email", "action": "get"}, {"tool": "langmodel", "action": "summarize"}],
        }
    ]

    tools = workflows_feature.get_tools()

    assert len(tools) == 1
    assert tools[0]["name"] == "Email Summary"
    assert tools[0]["type"] == "workflow"
    assert "Similarity: 95%" in tools[0]["description"]
    assert "{{name}}" in tools[0]["description"]  # Curly braces escaped
    assert "email.get()" in tools[0]["description"]


def test_get_tools_escapes_curly_braces(workflows_feature):
    """Test that get_tools properly escapes curly braces for LangChain."""
    workflows_feature._similar_workflows = [
        {
            "rank": 1,
            "similarity": 1.0,
            "workflow_id": "test-123",
            "name": "Test Workflow",
            "parameterized_prompt": "process {input} with {options}",
            "input_variables": {"input": "data", "options": "default"},
            "actions": [],
        }
    ]

    tools = workflows_feature.get_tools()

    description = tools[0]["description"]
    # Curly braces should be escaped
    assert "{{input}}" in description
    assert "{{options}}" in description
    # Should not contain unescaped braces
    assert description.count("{") == description.count("}")


def test_get_tools_returns_empty_when_no_workflows(workflows_feature):
    """Test get_tools returns empty list when no workflows cached."""
    workflows_feature._similar_workflows = []

    tools = workflows_feature.get_tools()

    assert tools == []


if __name__ == "__main__":
    print("Running workflow tool tests...")
    pytest.main([__file__, "-v"])
