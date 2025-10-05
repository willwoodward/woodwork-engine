"""
End-to-end integration test for workflow system.

This tests the complete flow:
1. Agent executes actions
2. Actions are captured in Neo4j graph
3. Similar workflows are retrieved
4. Workflows can be executed directly
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import json


class TestWorkflowEndToEnd:
    """End-to-end integration tests for workflow system."""

    @pytest.fixture
    def mock_neo4j_component(self):
        """Mock Neo4j that actually stores data."""
        neo4j = Mock()

        # Store data in memory for the mock
        neo4j._workflows = {}
        neo4j._prompts = {}
        neo4j._actions = {}
        neo4j._relationships = []

        def run_query(query, params=None):
            """Mock query execution with simple in-memory storage."""
            params = params or {}

            # Handle workflow creation
            if "CREATE (w:Workflow" in query:
                workflow_id = params.get("workflow_id")
                neo4j._workflows[workflow_id] = {
                    "id": workflow_id,
                    "status": params.get("status", "in_progress"),
                    "source": "auto"
                }

                # Also create prompt
                if "CREATE (p:Prompt" in query:
                    prompt_id = params.get("prompt_id")
                    neo4j._prompts[prompt_id] = {
                        "id": prompt_id,
                        "text": params.get("input_text", ""),
                        "workflow_id": workflow_id
                    }
                return [{"workflow_id": workflow_id}]

            # Handle action creation
            elif "CREATE (a:Action" in query:
                action_id = params.get("action_id")
                neo4j._actions[action_id] = {
                    "id": action_id,
                    "tool": params.get("tool"),
                    "action": params.get("action_name"),
                    "inputs": params.get("inputs_json"),
                    "output": params.get("output_var"),
                    "sequence": params.get("sequence"),
                    "workflow_id": params.get("workflow_id")
                }
                return [{"action_id": action_id}]

            # Handle relationship creation
            elif ("CREATE" in query or "MERGE" in query) and ("-[:" in query):
                neo4j._relationships.append({
                    "query": query,
                    "params": params
                })
                return []

            # Handle workflow completion
            elif "SET w.status = 'completed'" in query:
                workflow_id = params.get("workflow_id")
                if workflow_id in neo4j._workflows:
                    neo4j._workflows[workflow_id]["status"] = "completed"
                return [{"workflow_id": workflow_id}]

            # Handle action retrieval for execution
            elif "MATCH (w:Workflow {id:" in query and "RETURN a.id as id" in query:
                workflow_id = params.get("workflow_id")
                actions = [
                    action for action in neo4j._actions.values()
                    if action.get("workflow_id") == workflow_id
                ]
                # Sort by sequence
                actions.sort(key=lambda x: x.get("sequence", 0))
                return actions

            return []

        neo4j.run = Mock(side_effect=run_query)
        neo4j.init_vector_index = Mock()
        neo4j.similarity_search = Mock(return_value=[])

        return neo4j

    @pytest.fixture
    def workflows_feature(self, mock_neo4j_component):
        """Create WorkflowsFeature with mocked Neo4j."""
        from woodwork.components.internal_features.workflows import WorkflowsFeature

        feature = WorkflowsFeature()
        feature._neo4j_component = mock_neo4j_component

        # Mock component reference
        feature._component_ref = Mock()
        feature._component_ref.name = "test_agent"
        feature._component_ref.model = Mock()
        feature._component_ref.model._api_key = "test-api-key"

        return feature

    def test_workflow_capture_creates_all_nodes(self, workflows_feature, mock_neo4j_component):
        """Test that workflow capture creates Workflow, Prompt, and Action nodes."""
        from woodwork.types.events import InputReceivedPayload, AgentActionPayload

        # Start workflow
        input_payload = InputReceivedPayload(
            input="Process the data file",
            inputs={},
            session_id="test_session",
            component_id="test_agent",
            component_type="agent"
        )

        workflows_feature._check_similar_workflows_pipe(input_payload)

        # Verify workflow and prompt created
        assert len(mock_neo4j_component._workflows) == 1
        assert len(mock_neo4j_component._prompts) == 1

        # Add actions
        for i in range(3):
            action_data = {
                "tool": f"tool_{i}",
                "action": f"action_{i}",
                "inputs": {"input": f"value_{i}"},
                "output": f"output_{i}"
            }

            action_payload = AgentActionPayload(
                action=json.dumps(action_data),
                component_id="test_agent",
                component_type="agent"
            )

            workflows_feature._sync_action_hook(action_payload)

        # Verify all actions created
        assert len(mock_neo4j_component._actions) == 3

        # Verify relationships created
        relationship_queries = [r["query"] for r in mock_neo4j_component._relationships]

        # Should have STARTS, NEXT relationships
        assert any("STARTS" in q for q in relationship_queries)
        assert any("NEXT" in q for q in relationship_queries)

    def test_workflow_tracks_variable_dependencies(self, workflows_feature, mock_neo4j_component):
        """Test that workflow tracks dependencies between actions via variables."""
        from woodwork.types.events import InputReceivedPayload, AgentActionPayload

        # Start workflow
        input_payload = InputReceivedPayload(
            input="Process data",
            inputs={},
            session_id="test",
            component_id="test_agent",
            component_type="agent"
        )

        workflows_feature._check_similar_workflows_pipe(input_payload)

        # Action 1: Read file
        action1 = AgentActionPayload(
            action=json.dumps({
                "tool": "file_tool",
                "action": "read",
                "inputs": {"path": "data.txt"},
                "output": "file_contents"
            }),
            component_id="test_agent",
            component_type="agent"
        )
        workflows_feature._sync_action_hook(action1)

        # Action 2: Process (depends on action 1)
        action2 = AgentActionPayload(
            action=json.dumps({
                "tool": "process_tool",
                "action": "process",
                "inputs": {"data": "file_contents"},  # Uses output from action1
                "output": "result"
            }),
            component_id="test_agent",
            component_type="agent"
        )
        workflows_feature._sync_action_hook(action2)

        # Check that DEPENDS_ON relationship was created
        relationship_queries = [r["query"] for r in mock_neo4j_component._relationships]
        depends_on_queries = [q for q in relationship_queries if "DEPENDS_ON" in q]

        assert len(depends_on_queries) > 0, "Should create DEPENDS_ON relationship for variable dependency"

    def test_workflow_completion_marks_status(self, workflows_feature, mock_neo4j_component):
        """Test that workflow completion updates status."""
        from woodwork.types.events import InputReceivedPayload, AgentStepCompletePayload

        # Start workflow
        input_payload = InputReceivedPayload(
            input="Test task",
            inputs={},
            session_id="test",
            component_id="test_agent",
            component_type="agent"
        )

        workflows_feature._check_similar_workflows_pipe(input_payload)
        workflow_id = workflows_feature._current_workflow_id

        # Complete workflow
        complete_payload = AgentStepCompletePayload(
            step=5,
            session_id="test",
            component_id="test_agent",
            component_type="agent"
        )

        workflows_feature._complete_workflow_hook(complete_payload)

        # Verify workflow marked as completed
        assert mock_neo4j_component._workflows[workflow_id]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_workflow_executor_retrieves_and_executes(self, mock_neo4j_component):
        """Test that WorkflowExecutor can retrieve and execute a captured workflow."""
        from woodwork.components.internal_features.workflow_executor import WorkflowExecutor

        # Setup: Create a workflow with actions in Neo4j mock
        workflow_id = "test_workflow"
        mock_neo4j_component._workflows[workflow_id] = {"id": workflow_id}

        # Add actions
        mock_neo4j_component._actions["a1"] = {
            "id": "a1",
            "tool": "file_tool",
            "action": "read",
            "inputs": '{"path": "test.txt"}',
            "output": "file_data",
            "sequence": 0,
            "workflow_id": workflow_id
        }

        mock_neo4j_component._actions["a2"] = {
            "id": "a2",
            "tool": "text_tool",
            "action": "process",
            "inputs": '{"text": "file_data"}',  # Variable reference
            "output": "result",
            "sequence": 1,
            "workflow_id": workflow_id
        }

        # Mock task master with tools
        task_master = Mock()
        file_tool = Mock()
        file_tool.execute = AsyncMock(return_value="File content from test.txt")
        text_tool = Mock()
        text_tool.execute = AsyncMock(return_value="Processed: File content from test.txt")

        task_master.get_tool = Mock(side_effect=lambda name: {
            "file_tool": file_tool,
            "text_tool": text_tool
        }.get(name))

        # Execute workflow
        executor = WorkflowExecutor(mock_neo4j_component, task_master)
        result = await executor.execute_workflow(
            workflow_id=workflow_id,
            inputs={},
            session_id="test"
        )

        # Verify execution
        assert result['status'] == 'completed'
        assert len(result['results']) == 2
        assert 'file_data' in result['final_outputs']
        assert 'result' in result['final_outputs']

        # Verify variable substitution worked
        text_tool_call = text_tool.execute.call_args
        assert text_tool_call[1]['text'] == "File content from test.txt"  # Resolved!

    def test_full_workflow_lifecycle(self, workflows_feature, mock_neo4j_component):
        """Test complete lifecycle: capture -> complete -> verify storage."""
        from woodwork.types.events import (
            InputReceivedPayload,
            AgentActionPayload,
            AgentStepCompletePayload
        )

        # 1. Start workflow
        input_payload = InputReceivedPayload(
            input="Create a report from data",
            inputs={},
            session_id="test",
            component_id="test_agent",
            component_type="agent"
        )
        workflows_feature._check_similar_workflows_pipe(input_payload)
        workflow_id = workflows_feature._current_workflow_id

        # 2. Execute actions
        actions_data = [
            {"tool": "file_tool", "action": "read", "inputs": {"path": "data.csv"}, "output": "csv_data"},
            {"tool": "analysis_tool", "action": "analyze", "inputs": {"data": "csv_data"}, "output": "analysis"},
            {"tool": "report_tool", "action": "generate", "inputs": {"analysis": "analysis"}, "output": "report"}
        ]

        for action_data in actions_data:
            payload = AgentActionPayload(
                action=json.dumps(action_data),
                component_id="test_agent",
                component_type="agent"
            )
            workflows_feature._sync_action_hook(payload)

        # 3. Complete workflow
        complete_payload = AgentStepCompletePayload(
            step=len(actions_data),
            session_id="test",
            component_id="test_agent",
            component_type="agent"
        )
        workflows_feature._complete_workflow_hook(complete_payload)

        # 4. Verify complete workflow in storage
        assert workflow_id in mock_neo4j_component._workflows
        assert mock_neo4j_component._workflows[workflow_id]["status"] == "completed"
        assert len(mock_neo4j_component._actions) == 3

        # Verify first action has STARTS relationship
        starts_rels = [r for r in mock_neo4j_component._relationships if "STARTS" in r["query"]]
        assert len(starts_rels) == 1

        # Verify sequential NEXT relationships
        next_rels = [r for r in mock_neo4j_component._relationships if "NEXT" in r["query"]]
        assert len(next_rels) == 2  # Between 3 actions

        # Verify dependency relationships
        depends_rels = [r for r in mock_neo4j_component._relationships if "DEPENDS_ON" in r["query"]]
        assert len(depends_rels) >= 2  # action2 depends on action1, action3 on action2
