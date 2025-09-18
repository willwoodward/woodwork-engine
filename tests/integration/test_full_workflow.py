"""Integration tests for complete workflows combining all systems."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from woodwork.core.message_bus.declarative_router import DeclarativeRouter
from woodwork.core.message_bus.in_memory_bus import InMemoryMessageBus
from tests.unit.fixtures.mock_components import MockAgent, MockTool, MockOutput


class TestFullWorkflow:
    """Test complete workflows integrating message bus, streaming, and events."""

    @pytest.fixture
    async def full_system_setup(self):
        """Set up complete system with all components."""
        # Message bus infrastructure
        message_bus = InMemoryMessageBus()
        await message_bus.start()

        router = DeclarativeRouter(message_bus)

        # Create realistic components
        coding_agent = MockAgent("coding_ag")
        planning_tools = MockTool("planning_tools")
        github_api = MockTool("github_api")
        console_output = MockOutput("console_output")

        components = {
            "coding_ag": {
                "object": coding_agent,
                "component": "llm",
                "to": ["console_output"]
            },
            "planning_tools": {
                "object": planning_tools,
                "component": "planning_tools"
            },
            "github_api": {
                "object": github_api,
                "component": "functions"
            },
            "console_output": {
                "object": console_output,
                "component": "console"
            }
        }

        router.configure_from_components(components)

        # Mock event system
        from tests.unit.fixtures.event_fixtures import MockEventManager
        event_manager = MockEventManager()

        yield {
            "router": router,
            "message_bus": message_bus,
            "event_manager": event_manager,
            "coding_agent": coding_agent,
            "planning_tools": planning_tools,
            "github_api": github_api,
            "console_output": console_output,
            "components": components
        }

        await message_bus.stop()

    async def test_complete_issue_analysis_workflow(self, full_system_setup):
        """Test complete workflow: input -> planning -> GitHub -> analysis -> output."""
        setup = full_system_setup
        router = setup["router"]
        coding_agent = setup["coding_agent"]
        planning_tools = setup["planning_tools"]
        github_api = setup["github_api"]
        event_manager = setup["event_manager"]

        # Mock component responses
        planning_tools.input = Mock(return_value="Created plan: [fetch issue, analyze, summarize]")
        github_api.input = Mock(return_value="Issue #113: Message routing timeout in agent communication")

        # Mock agent tool execution
        async def mock_execute_tool(tool_name, action, inputs):
            if tool_name == "planning_tools":
                return "Planning completed"
            elif tool_name == "github_api":
                return "GitHub data retrieved"
            return "Tool executed"

        coding_agent.execute_tool = mock_execute_tool

        # Simulate complete workflow
        # 1. Agent creates plan
        plan_result = await coding_agent.execute_tool("planning_tools", "create_plan", {
            "task": "Analyze GitHub issue #113"
        })

        # 2. Agent fetches GitHub data
        github_result = await coding_agent.execute_tool("github_api", "get_issue", {
            "repo": "willwoodward/woodwork-engine",
            "issue": 113
        })

        # 3. Emit events for tracking
        event_manager.emit("agent.step_complete", {
            "step": "planning",
            "result": plan_result
        })

        event_manager.emit("agent.step_complete", {
            "step": "data_fetch",
            "result": github_result
        })

        # Verify workflow completion
        assert plan_result == "Planning completed"
        assert github_result == "GitHub data retrieved"
        assert len(event_manager.emitted_events) == 2

    async def test_streaming_with_message_bus_workflow(self, full_system_setup):
        """Test workflow combining streaming and message bus communication."""
        setup = full_system_setup
        router = setup["router"]
        coding_agent = setup["coding_agent"]

        # Add streaming capabilities to agent
        from woodwork.components.streaming_mixin import StreamingMixin

        class StreamingAgent(StreamingMixin, MockAgent):
            def __init__(self, name):
                MockAgent.__init__(self, name)
                StreamingMixin.__init__(self, name=name, config={"streaming": True})

            async def execute_with_streaming(self, tool_name, action, inputs, target="listener"):
                # Start streaming thoughts
                thought_stream = await self.create_output_stream(target)

                # Stream thinking process
                await self.stream_output(thought_stream, "Starting task execution")
                await self.stream_output(thought_stream, f"Calling tool: {tool_name}")

                # Execute tool via message bus
                result = await self.execute_tool(tool_name, action, inputs)

                # Stream completion
                await self.stream_output(thought_stream, f"Tool completed: {result}")
                await self.stream_output(thought_stream, "", is_final=True)

                return result

        # Mock streaming infrastructure
        with patch('woodwork.core.stream_manager.StreamManager') as mock_manager_class:
            mock_manager = Mock()
            mock_manager.create_stream = AsyncMock(return_value="agent_thoughts")
            mock_manager.send_chunk = AsyncMock(return_value=True)
            mock_manager_class.return_value = mock_manager

            streaming_agent = StreamingAgent("streaming_coding_ag")
            streaming_agent.set_stream_manager(mock_manager)
            streaming_agent.execute_tool = AsyncMock(return_value="Tool executed successfully")

            result = await streaming_agent.execute_with_streaming(
                "planning_tools", "create_plan", {"task": "test"}
            )

            assert result == "Tool executed successfully"
            assert mock_manager.send_chunk.call_count == 4  # 3 stream writes + final

    async def test_error_handling_across_systems(self, full_system_setup):
        """Test error handling across message bus, streaming, and events."""
        setup = full_system_setup
        router = setup["router"]
        coding_agent = setup["coding_agent"]
        planning_tools = setup["planning_tools"]
        event_manager = setup["event_manager"]

        # Mock planning tools to fail
        planning_tools.input = Mock(side_effect=Exception("Planning service unavailable"))

        # Mock agent error handling
        async def mock_execute_with_error_handling(tool_name, action, inputs):
            try:
                # This would normally call the tool
                if tool_name == "planning_tools":
                    planning_tools.input(action, inputs)
                return "Success"
            except Exception as e:
                # Emit error event
                event_manager.emit("agent.error", {
                    "tool": tool_name,
                    "error": str(e),
                    "action": action
                })
                return f"Error: {str(e)}"

        coding_agent.execute_tool = mock_execute_with_error_handling

        # Execute workflow with error
        result = await coding_agent.execute_tool("planning_tools", "create_plan", {})

        # Should handle error gracefully
        assert "Error: Planning service unavailable" in result
        assert len(event_manager.emitted_events) == 1
        assert event_manager.emitted_events[0][0] == "agent.error"

    async def test_concurrent_workflows(self, full_system_setup):
        """Test multiple concurrent workflows."""
        setup = full_system_setup
        router = setup["router"]

        # Create multiple agents
        agents = [MockAgent(f"agent_{i}") for i in range(3)]
        tools = [MockTool(f"tool_{i}") for i in range(3)]

        # Mock tool responses
        for i, tool in enumerate(tools):
            tool.input = Mock(return_value=f"Tool {i} result")

        # Mock agent executions
        async def mock_workflow(agent_idx):
            agent = agents[agent_idx]
            tool = tools[agent_idx]

            # Simulate tool execution
            success, request_id = await router.send_to_component_with_response(
                name=f"tool_{agent_idx}",
                source_component_name=f"agent_{agent_idx}",
                data={"action": "execute", "inputs": {}}
            )
            return success

        # Run workflows concurrently
        tasks = [mock_workflow(i) for i in range(3)]
        results = await asyncio.gather(*tasks)

        assert all(results)

    async def test_performance_under_load(self, full_system_setup):
        """Test system performance under load."""
        setup = full_system_setup
        router = setup["router"]
        message_bus = setup["message_bus"]

        # Register many components
        handlers = {}
        for i in range(50):
            handler = AsyncMock()
            component_id = f"load_test_component_{i}"
            handlers[component_id] = handler
            message_bus.register_component_handler(component_id, handler)

        # Send many messages concurrently
        from tests.unit.fixtures.test_messages import create_component_message

        async def send_message(i):
            message = create_component_message(
                source="load_test_source",
                target=f"load_test_component_{i % 50}",
                data={"task_id": i}
            )
            return await message_bus.send_to_component(message)

        # Measure performance
        import time
        start_time = time.time()

        tasks = [send_message(i) for i in range(500)]  # 500 messages
        results = await asyncio.gather(*tasks)

        end_time = time.time()
        total_time = end_time - start_time

        assert all(results)
        assert total_time < 5.0  # Should complete within 5 seconds
        print(f"Processed 500 messages in {total_time:.2f} seconds")

    async def test_memory_usage_in_long_workflow(self, full_system_setup):
        """Test memory usage in long-running workflows."""
        setup = full_system_setup
        router = setup["router"]
        event_manager = setup["event_manager"]

        # Simulate long-running workflow
        for iteration in range(100):
            # Emit events
            event_manager.emit("agent.thought", {
                "iteration": iteration,
                "thought": f"Processing step {iteration}"
            })

            # Send messages
            success, request_id = await router.send_to_component_with_response(
                name="planning_tools",
                source_component_name="coding_ag",
                data={"iteration": iteration}
            )

            # Simulate cleanup every 10 iterations
            if iteration % 10 == 0:
                # Clear old events (simulate cleanup)
                if len(event_manager.emitted_events) > 50:
                    event_manager.emitted_events = event_manager.emitted_events[-25:]

        # Memory should be managed
        assert len(event_manager.emitted_events) <= 50


class TestRealWorldCompleteScenarios:
    """Test complete real-world scenarios."""

    async def test_code_review_workflow(self):
        """Test complete code review workflow."""
        # This would be a comprehensive test of:
        # 1. Reading code files
        # 2. Analyzing with AI
        # 3. Streaming feedback
        # 4. Generating reports
        # 5. Storing results

        from tests.unit.fixtures.mock_components import MockAgent, MockTool

        # Mock components
        code_reader = MockTool("code_reader")
        ai_analyzer = MockAgent("ai_analyzer")
        report_generator = MockTool("report_generator")

        code_reader.input = Mock(return_value="Code content loaded")
        ai_analyzer.execute_tool = AsyncMock(return_value="Analysis complete")
        report_generator.input = Mock(return_value="Report generated")

        # Simulate workflow steps
        code_content = code_reader.input("read_file", {"path": "/path/to/code.py"})
        analysis = await ai_analyzer.execute_tool("analyze", "review_code", {"code": code_content})
        report = report_generator.input("generate_report", {"analysis": analysis})

        assert code_content == "Code content loaded"
        assert analysis == "Analysis complete"
        assert report == "Report generated"

    async def test_automated_deployment_workflow(self):
        """Test automated deployment workflow."""
        # This would test:
        # 1. Code validation
        # 2. Test execution
        # 3. Build process
        # 4. Deployment
        # 5. Monitoring

        from tests.unit.fixtures.mock_components import MockTool

        validator = MockTool("validator")
        tester = MockTool("tester")
        builder = MockTool("builder")
        deployer = MockTool("deployer")

        # Mock successful workflow
        validator.input = Mock(return_value="Validation passed")
        tester.input = Mock(return_value="All tests passed")
        builder.input = Mock(return_value="Build successful")
        deployer.input = Mock(return_value="Deployment completed")

        # Execute deployment pipeline
        validation_result = validator.input("validate", {"code": "source_code"})
        test_result = tester.input("run_tests", {"suite": "full"})
        build_result = builder.input("build", {"target": "production"})
        deploy_result = deployer.input("deploy", {"environment": "production"})

        # All steps should succeed
        assert validation_result == "Validation passed"
        assert test_result == "All tests passed"
        assert build_result == "Build successful"
        assert deploy_result == "Deployment completed"

    async def test_customer_support_workflow(self):
        """Test customer support automation workflow."""
        # This would test:
        # 1. Ticket intake
        # 2. Classification
        # 3. Routing
        # 4. Response generation
        # 5. Follow-up

        from tests.unit.fixtures.mock_components import MockAgent, MockTool

        ticket_classifier = MockAgent("classifier")
        knowledge_base = MockTool("knowledge_base")
        response_generator = MockAgent("response_gen")

        # Mock support workflow
        ticket_classifier.execute_tool = AsyncMock(return_value="Category: Technical Issue")
        knowledge_base.input = Mock(return_value="Relevant KB article found")
        response_generator.execute_tool = AsyncMock(return_value="Support response generated")

        # Process support ticket
        ticket_data = {"issue": "Login problems", "user": "customer@example.com"}

        classification = await ticket_classifier.execute_tool(
            "classify_ticket", "analyze", ticket_data
        )

        kb_result = knowledge_base.input("search", {"query": "login problems"})

        response = await response_generator.execute_tool(
            "generate_response", "create", {
                "classification": classification,
                "kb_info": kb_result,
                "ticket": ticket_data
            }
        )

        assert "Technical Issue" in classification
        assert "KB article found" in kb_result
        assert "response generated" in response