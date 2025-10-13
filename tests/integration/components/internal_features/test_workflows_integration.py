"""Integration tests for WorkflowsFeature with real component interaction."""

import pytest
from unittest.mock import Mock, patch


@pytest.mark.integration
@pytest.mark.workflows
class TestWorkflowsIntegration:
    """Integration tests for workflows feature with LLM agents."""

    @patch('woodwork.components.knowledge_bases.graph_databases.neo4j.neo4j')
    def test_workflows_feature_with_llm_agent(self, mock_neo4j_factory):
        """Test workflows feature integration with LLM agent."""
        # Setup mock Neo4j
        mock_neo4j_instance = Mock()
        mock_neo4j_instance.init_vector_index = Mock()
        mock_neo4j_instance.run = Mock(return_value=[])
        mock_neo4j_instance.similarity_search = Mock(return_value=[])
        mock_neo4j_factory.return_value = mock_neo4j_instance

        # Mock agent with internal component manager
        class MockAgent:
            def __init__(self, name):
                self.name = name
                from woodwork.components.internal_features.base import InternalComponentManager
                self._internal_component_manager = InternalComponentManager()

                # Mock model with API key
                self.model = Mock()
                self.model._api_key = "test-api-key"

        # Create agent
        agent = MockAgent("workflows_test_agent")

        # Create workflows feature
        from woodwork.components.internal_features.workflows import WorkflowsFeature
        feature = WorkflowsFeature()

        # Setup feature
        config = {"workflows": True}
        feature._setup_feature(agent, config, agent._internal_component_manager)

        # Verify feature was set up correctly
        assert hasattr(agent, '_workflows_db')
        assert hasattr(agent, '_workflows_mode')
        assert agent._workflows_db is mock_neo4j_instance
        assert agent._workflows_mode is True

        # Verify Neo4j component was created
        assert mock_neo4j_factory.called

        # Verify vector indices were initialized
        assert mock_neo4j_instance.init_vector_index.call_count == 2

        print("✅ Workflows feature integration with LLM agent working!")

    def test_workflows_feature_hooks_and_pipes_registration(self):
        """Test that workflows feature hooks and pipes are properly registered."""
        from woodwork.components.internal_features.workflows import WorkflowsFeature

        feature = WorkflowsFeature()

        # Test hooks
        hooks = feature.get_hooks()
        assert len(hooks) == 2

        hook_events = [hook[0] for hook in hooks]
        assert "agent.action" in hook_events
        assert "agent.step_complete" in hook_events

        # Test pipes
        pipes = feature.get_pipes()
        assert len(pipes) == 1
        assert pipes[0][0] == "input.received"

        # Test that hook/pipe functions are callable
        for event, func in hooks:
            assert callable(func)

        for event, func in pipes:
            assert callable(func)

        print("✅ Workflows feature hooks and pipes properly registered!")

    @patch('woodwork.components.knowledge_bases.graph_databases.neo4j.neo4j')
    def test_workflows_feature_end_to_end_simulation(self, mock_neo4j_factory):
        """Test complete workflow simulation from input to completion."""
        # Setup mock Neo4j
        mock_neo4j_instance = Mock()
        mock_neo4j_instance.init_vector_index = Mock()
        mock_neo4j_instance.run = Mock(return_value=[])
        mock_neo4j_instance.similarity_search = Mock(return_value=[])
        mock_neo4j_factory.return_value = mock_neo4j_instance

        # Create workflows feature
        from woodwork.components.internal_features.workflows import WorkflowsFeature
        from woodwork.components.internal_features.base import InternalComponentManager
        from woodwork.types.events import InputReceivedPayload, AgentActionPayload, AgentStepCompletePayload

        feature = WorkflowsFeature()

        # Mock agent
        agent = Mock()
        agent.name = "test_agent"
        agent.model = Mock()
        agent.model._api_key = "test-api-key"

        # Setup feature
        component_manager = InternalComponentManager()
        feature._setup_feature(agent, {}, component_manager)

        # 1. Test input pipe (no similar workflows)
        input_payload = InputReceivedPayload(
            input="Create a new file and write content",
            inputs={},
            session_id="test_session",
            component_id="test_agent",
            component_type="agent"
        )

        result_payload = feature._check_similar_workflows_pipe(input_payload)
        assert result_payload.input == input_payload.input  # No similar workflows found
        assert feature._current_workflow_id is not None  # New workflow started

        # 2. Test action sync hook (first action)
        action_payload_1 = AgentActionPayload(
            action='{"tool": "file_tool", "action": "create", "inputs": {"filename": "test.txt"}, "output": "file_created"}',
            component_id="test_agent",
            component_type="agent"
        )

        feature._sync_action_hook(action_payload_1)
        assert len(feature._workflow_actions) == 1

        # 3. Test action sync hook (second action with dependency)
        action_payload_2 = AgentActionPayload(
            action='{"tool": "text_tool", "action": "write", "inputs": {"file": "file_created", "content": "Hello World"}, "output": "content_written"}',
            component_id="test_agent",
            component_type="agent"
        )

        feature._sync_action_hook(action_payload_2)
        assert len(feature._workflow_actions) == 2

        # 4. Test workflow completion hook
        completion_payload = AgentStepCompletePayload(
            result="File created and content written successfully",
            component_id="test_agent",
            component_type="agent"
        )

        feature._complete_workflow_hook(completion_payload)
        assert feature._current_workflow_id is None  # Workflow completed and reset
        assert feature._workflow_actions == []

        # Verify Neo4j was called for all operations
        assert mock_neo4j_instance.run.call_count >= 4  # Workflow creation, actions, relationships, completion

        print("✅ End-to-end workflows feature simulation working!")

    def test_workflows_feature_registry_integration(self):
        """Test that workflows feature is properly registered in the registry."""
        from woodwork.components.internal_features.base import InternalFeatureRegistry
        from woodwork.components.internal_features.workflows import WorkflowsFeature

        # Test feature creation from registry
        features = InternalFeatureRegistry.create_features({"workflows": True})

        assert len(features) == 1
        assert isinstance(features[0], WorkflowsFeature)

        print("✅ Workflows feature registry integration working!")

    def test_workflows_config_variations(self):
        """Test different configuration options for workflows feature."""
        from woodwork.components.internal_features.base import InternalFeatureRegistry

        # Test basic config
        features_1 = InternalFeatureRegistry.create_features({"workflows": True})
        assert len(features_1) == 1

        # Test with custom Neo4j settings (should still work)
        features_2 = InternalFeatureRegistry.create_features({
            "workflows": True,
            "workflows_uri": "bolt://custom:7687",
            "workflows_user": "custom_user",
            "workflows_password": "custom_pass"
        })
        assert len(features_2) == 1

        # Test disabled
        features_3 = InternalFeatureRegistry.create_features({"workflows": False})
        assert len(features_3) == 0

        # Test not specified
        features_4 = InternalFeatureRegistry.create_features({})
        workflows_features = [f for f in features_4 if f.__class__.__name__ == "WorkflowsFeature"]
        assert len(workflows_features) == 0

        print("✅ Workflows feature configuration variations working!")

    @patch('woodwork.components.knowledge_bases.graph_databases.neo4j.neo4j')
    def test_workflows_feature_with_existing_workflow_context(self, mock_neo4j_factory):
        """Test workflows feature when similar workflows exist."""
        # Setup mock Neo4j with existing workflow
        mock_neo4j_instance = Mock()
        mock_neo4j_instance.init_vector_index = Mock()
        mock_neo4j_instance.run = Mock()
        mock_neo4j_instance.similarity_search = Mock(return_value=[
            {
                "nodeID": "existing-prompt-123",
                "score": 0.92,
                "text": "Create a file and add content"
            }
        ])

        # Mock workflow context query result
        def mock_run_side_effect(query, params=None):
            if "MATCH (p:Prompt)" in query and "path = (first)-[:NEXT*0..10]->" in query:
                return [
                    {
                        "prompt": "Create a file and add content",
                        "workflow": [
                            {"tool": "file_tool", "action": "create", "output": "file_created"},
                            {"tool": "text_tool", "action": "write", "output": "content_added"}
                        ]
                    }
                ]
            return []

        mock_neo4j_instance.run.side_effect = mock_run_side_effect
        mock_neo4j_factory.return_value = mock_neo4j_instance

        # Create feature and setup
        from woodwork.components.internal_features.workflows import WorkflowsFeature
        from woodwork.components.internal_features.base import InternalComponentManager
        from woodwork.types.events import InputReceivedPayload

        feature = WorkflowsFeature()

        agent = Mock()
        agent.name = "test_agent"
        agent.model = Mock()
        agent.model._api_key = "test-api-key"

        component_manager = InternalComponentManager()
        feature._setup_feature(agent, {}, component_manager)

        # Test input with similar existing workflow
        input_payload = InputReceivedPayload(
            input="Create a file and write some content",
            inputs={},
            session_id="test_session",
            component_id="test_agent",
            component_type="agent"
        )

        result_payload = feature._check_similar_workflows_pipe(input_payload)

        # Should have enhanced input with workflow context
        assert "[Similar Workflow Context]:" in result_payload.input
        assert "Use file_tool to create" in result_payload.input
        assert "Use text_tool to write" in result_payload.input

        print("✅ Workflows feature with existing workflow context working!")

    def test_workflows_feature_teardown_integration(self):
        """Test proper teardown of workflows feature."""
        from woodwork.components.internal_features.workflows import WorkflowsFeature
        from woodwork.components.internal_features.base import InternalComponentManager

        # Create feature
        feature = WorkflowsFeature()

        # Mock agent
        agent = Mock()
        agent.name = "test_agent"
        agent.model = Mock()
        agent.model._api_key = "test-api-key"

        # Setup and then teardown
        component_manager = InternalComponentManager()

        with patch('woodwork.components.knowledge_bases.graph_databases.neo4j.neo4j'):
            feature._setup_feature(agent, {}, component_manager)

            # Verify setup
            assert hasattr(agent, '_workflows_db')
            assert hasattr(agent, '_workflows_mode')

            # Teardown
            feature.teardown(agent, component_manager)

            # Verify cleanup
            assert not hasattr(agent, '_workflows_db')
            assert not hasattr(agent, '_workflows_mode')
            assert feature._neo4j_component is None

        print("✅ Workflows feature teardown integration working!")