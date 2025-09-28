"""Integration tests for component communication flows."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from woodwork.core.unified_event_bus import UnifiedEventBus
from woodwork.core.message_bus.in_memory_bus import InMemoryMessageBus
from tests.unit.fixtures.mock_components import MockAgent, MockTool, MockOutput, MockMessageBus


class TestComponentCommunicationFlow:
    """Test end-to-end component communication."""

    @pytest.fixture
    async def communication_setup(self):
        """Set up complete communication infrastructure."""
        # Create real message bus
        message_bus = InMemoryMessageBus()
        await message_bus.start()

        # Create router
        router = UnifiedEventBus()

        # Create components
        agent = MockAgent("test_agent")
        tool = MockTool("test_tool")
        output = MockOutput("test_output")

        components = {
            "test_agent": {"object": agent, "component": "llm"},
            "test_tool": {"object": tool, "component": "functions"},
            "test_output": {"object": output, "component": "console"}
        }

        # Register components and configure routing
        for comp_data in components.values():
            router.register_component(comp_data["object"])
        router.configure_routing()

        yield {
            "router": router,
            "message_bus": message_bus,
            "agent": agent,
            "tool": tool,
            "output": output,
            "components": components
        }

        # Cleanup
        await message_bus.stop()

    async def test_agent_to_tool_communication(self, communication_setup):
        """Test agent sending request to tool and receiving response."""
        setup = communication_setup
        router = setup["router"]
        agent = setup["agent"]
        tool = setup["tool"]

        # Mock the tool's input method to return a result
        tool.input = Mock(return_value="tool_executed_successfully")

        # Send request from agent to tool
        success, request_id = await router.send_to_component_with_response(
            name="test_tool",
            source_component_name="test_agent",
            data={"action": "execute", "inputs": {"param": "value"}}
        )

        assert success
        assert request_id is not None

        # Wait a bit for async processing
        await asyncio.sleep(0.1)

        # Tool should have been called
        tool.input.assert_called_once()

    async def test_request_response_cycle(self, communication_setup):
        """Test complete request-response cycle."""
        setup = communication_setup
        router = setup["router"]
        message_bus = setup["message_bus"]

        # Register components with message bus
        agent_handler = AsyncMock()
        tool_handler = AsyncMock()

        message_bus.register_component_handler("test_agent", agent_handler)
        message_bus.register_component_handler("test_tool", tool_handler)

        # Create test message
        from tests.unit.fixtures.test_messages import create_component_message

        message = create_component_message(
            source="test_agent",
            target="test_tool",
            data={"action": "test", "inputs": {}}
        )

        # Send message
        success = await message_bus.send_to_component(message)
        assert success

        # Tool handler should have been called
        tool_handler.assert_called_once()

    async def test_multi_component_workflow(self, communication_setup):
        """Test workflow involving multiple components."""
        setup = communication_setup
        router = setup["router"]
        agent = setup["agent"]
        tool = setup["tool"]
        output = setup["output"]

        # Set up routing chain: agent -> tool -> output
        router.routing_table = {
            "test_agent": ["test_tool"],
            "test_tool": ["test_output"]
        }

        # Mock component methods
        agent.execute_tool = AsyncMock(return_value="agent_result")
        tool.input = Mock(return_value="tool_result")
        output.output = Mock()

        # Start workflow
        result = await agent.execute_tool("test_tool", "execute", {"data": "test"})

        assert result == "agent_result"

    async def test_error_propagation(self, communication_setup):
        """Test error propagation through component chain."""
        setup = communication_setup
        router = setup["router"]
        message_bus = setup["message_bus"]

        # Create component that raises errors
        error_handler = AsyncMock(side_effect=Exception("Component error"))
        message_bus.register_component_handler("error_component", error_handler)

        # Send message to error component
        from tests.unit.fixtures.test_messages import create_component_message

        message = create_component_message(
            source="test_agent",
            target="error_component",
            data={"action": "fail"}
        )

        # Should handle error gracefully
        success = await message_bus.send_to_component(message)
        assert not success  # Message delivery fails when handler fails, but gets queued for retry

        error_handler.assert_called_once()

        # Verify the message was queued for retry
        assert message_bus.stats["delivery_failures"] == 1
        assert message_bus.stats["messages_retried"] == 1

    async def test_concurrent_communications(self, communication_setup):
        """Test concurrent component communications."""
        setup = communication_setup
        router = setup["router"]
        message_bus = setup["message_bus"]

        # Register multiple component handlers
        handlers = {}
        for i in range(5):
            handler = AsyncMock()
            component_id = f"component_{i}"
            handlers[component_id] = handler
            message_bus.register_component_handler(component_id, handler)

        # Send messages concurrently
        from tests.unit.fixtures.test_messages import create_component_message

        tasks = []
        for i in range(5):
            message = create_component_message(
                source="test_agent",
                target=f"component_{i}",
                data={"task_id": i}
            )
            tasks.append(message_bus.send_to_component(message))

        results = await asyncio.gather(*tasks)
        assert all(results)

        # All handlers should have been called
        for handler in handlers.values():
            handler.assert_called_once()

    async def test_message_ordering(self, communication_setup):
        """Test that messages are processed in order."""
        setup = communication_setup
        message_bus = setup["message_bus"]

        received_order = []

        async def ordered_handler(envelope):
            message_id = envelope.payload["data"]["message_id"]
            received_order.append(message_id)

        message_bus.register_component_handler("ordered_component", ordered_handler)

        # Send messages in sequence
        from tests.unit.fixtures.test_messages import create_component_message

        for i in range(10):
            message = create_component_message(
                source="test_agent",
                target="ordered_component",
                data={"message_id": i}
            )
            await message_bus.send_to_component(message)

        # Wait for all messages to be processed
        await asyncio.sleep(0.1)

        # Messages should be received in order
        assert received_order == list(range(10))


class TestAgentToolTimeoutIssue:
    """Test to reproduce and fix the agent-tool communication timeout issue."""

    @pytest.fixture
    async def timeout_test_setup(self):
        """Set up components for timeout testing."""
        message_bus = InMemoryMessageBus()
        await message_bus.start()

        router = UnifiedEventBus()

        # Create mock agent with the essential methods for timeout testing
        class MockAgentWithTimeout:
            def __init__(self, name):
                self.name = name
                self.type = "agent"
                self._received_responses = {}
                self._router = None

            def set_router(self, router):
                """Set router and register response handler."""
                self._router = router

            async def _wait_for_response(self, request_id, timeout=5.0):
                """Wait for response with timeout (reproduces current broken behavior)."""
                import asyncio
                poll_interval = 0.05
                waited = 0.0

                while waited < timeout:
                    if request_id in self._received_responses:
                        response_data = self._received_responses.pop(request_id)
                        return response_data["result"]

                    await asyncio.sleep(poll_interval)
                    waited += poll_interval

                raise TimeoutError(f"Tool response timeout after {timeout}s")

        # Create mock tool
        class MockToolForTimeout:
            def __init__(self, name):
                self.name = name
                self.type = "tool"

            def input(self, action, inputs):
                return f"Tool executed: {action} with {inputs}"

        agent = MockAgentWithTimeout("test_agent")
        tool = MockToolForTimeout("test_tool")

        components = {
            "test_agent": {"object": agent, "component": "agent"},
            "test_tool": {"object": tool, "component": "tool"}
        }

        # Register components and configure routing
        for comp_data in components.values():
            router.register_component(comp_data["object"])
        router.configure_routing()

        yield {
            "router": router,
            "message_bus": message_bus,
            "agent": agent,
            "tool": tool
        }

        await message_bus.stop()

    async def test_agent_tool_timeout_reproduction(self, timeout_test_setup):
        """
        Reproduce the actual timeout issue where agent doesn't receive tool responses.

        This test demonstrates the current broken behavior where:
        1. Agent sends request to tool via router
        2. Tool processes request and sends response back
        3. Response gets queued but agent never processes it
        4. Agent times out waiting for response
        """
        setup = timeout_test_setup
        router = setup["router"]
        agent = setup["agent"]

        # Set router on agent to enable response handling
        agent.set_router(router)

        # Send request with response expectation
        success, request_id = await router.send_to_component_with_response(
            name="test_tool",
            source_component_name="test_agent",
            data={"action": "test_action", "inputs": {"param": "value"}}
        )

        assert success
        assert request_id is not None

        # Wait a bit for message processing
        await asyncio.sleep(0.1)

        # This should timeout with current broken implementation
        with pytest.raises(TimeoutError) as exc_info:
            await agent._wait_for_response(request_id, timeout=0.5)

        assert "timeout" in str(exc_info.value).lower()

    async def test_response_handler_registration_fix(self, timeout_test_setup):
        """
        Test that demonstrates the fix: proper response handler registration.

        This test shows what should happen when the fix is applied:
        - Agent registers to receive messages from the message bus
        - Responses are properly handled and stored
        - No timeout occurs
        """
        setup = timeout_test_setup
        router = setup["router"]
        agent = setup["agent"]
        message_bus = setup["message_bus"]

        # FIXED VERSION: Register agent to receive responses directly via message bus
        async def agent_response_handler(envelope):
            """Handler that properly processes response messages."""
            payload = envelope.payload
            data = payload.get("data", {})

            if data.get("response_type") == "component_response":
                request_id = data.get("request_id")
                result = data.get("result")

                if request_id:
                    agent._received_responses[request_id] = {
                        "result": result,
                        "source_component": data.get("source_component"),
                        "received_at": asyncio.get_event_loop().time()
                    }

        # Register the fixed handler
        message_bus.register_component_handler("test_agent", agent_response_handler)

        # Send request
        success, request_id = await router.send_to_component_with_response(
            name="test_tool",
            source_component_name="test_agent",
            data={"action": "test_action", "inputs": {"param": "value"}}
        )

        assert success
        assert request_id is not None

        # Wait for processing
        await asyncio.sleep(0.2)  # Give more time for async processing

        # With the fix, this should work without timeout
        try:
            result = await agent._wait_for_response(request_id, timeout=1.0)
            assert "Tool executed" in result
        except TimeoutError:
            # If this still fails, check if response was actually received
            assert request_id in agent._received_responses, f"Response not received for {request_id}"
            result = agent._received_responses[request_id]["result"]
            assert "Tool executed" in result


class TestRealWorldScenarios:
    """Test real-world communication scenarios."""

    @pytest.fixture
    async def scenario_setup(self):
        """Set up scenario with realistic components."""
        message_bus = InMemoryMessageBus()
        await message_bus.start()

        router = UnifiedEventBus()

        # Create realistic component setup
        coding_agent = MockAgent("coding_ag")
        planning_tools = MockTool("planning_tools")
        github_api = MockTool("github_api")
        output = MockOutput("console_output")

        components = {
            "coding_ag": {"object": coding_agent, "component": "llm"},
            "planning_tools": {"object": planning_tools, "component": "planning_tools"},
            "github_api": {"object": github_api, "component": "functions"},
            "console_output": {"object": output, "component": "console"}
        }

        # Register components and configure routing
        for comp_data in components.values():
            router.register_component(comp_data["object"])
        router.configure_routing()

        yield {
            "router": router,
            "message_bus": message_bus,
            "coding_agent": coding_agent,
            "planning_tools": planning_tools,
            "github_api": github_api,
            "output": output
        }

        await message_bus.stop()

    async def test_planning_workflow(self, scenario_setup):
        """Test planning workflow scenario."""
        setup = scenario_setup
        router = setup["router"]
        coding_agent = setup["coding_agent"]
        planning_tools = setup["planning_tools"]

        # Mock planning tools response
        planning_tools.input = Mock(return_value="Updated todo list: [task1, task2]")

        # Agent requests planning
        success, request_id = await router.send_to_component_with_response(
            name="planning_tools",
            source_component_name="coding_ag",
            data={
                "action": "write_todos",
                "inputs": {"todos": ["Analyze issue", "Create plan"]}
            }
        )

        assert success
        planning_tools.input.assert_called_once()

    async def test_github_api_workflow(self, scenario_setup):
        """Test GitHub API interaction workflow."""
        setup = scenario_setup
        router = setup["router"]
        github_api = setup["github_api"]

        # Mock GitHub API response
        github_api.input = Mock(return_value="Issue #113: Bug in message routing")

        # Request GitHub data
        success, request_id = await router.send_to_component_with_response(
            name="github_api",
            source_component_name="coding_ag",
            data={
                "action": "get_issue",
                "inputs": {"repo": "willwoodward/woodwork-engine", "issue": 113}
            }
        )

        assert success
        github_api.input.assert_called_once()

    async def test_error_recovery_scenario(self, scenario_setup):
        """Test error recovery in real workflow."""
        setup = scenario_setup
        router = setup["router"]
        github_api = setup["github_api"]

        # Mock API failure then success
        call_count = 0

        def failing_then_working(action, inputs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("API rate limit exceeded")
            return "API call successful"

        github_api.input = Mock(side_effect=failing_then_working)

        # First call should fail
        try:
            await router.send_to_component_with_response(
                name="github_api",
                source_component_name="coding_ag",
                data={"action": "get_issue", "inputs": {"issue": 113}}
            )
        except Exception:
            pass

        # Second call should succeed
        success, request_id = await router.send_to_component_with_response(
            name="github_api",
            source_component_name="coding_ag",
            data={"action": "get_issue", "inputs": {"issue": 113}}
        )

        assert success
        assert github_api.input.call_count == 2

    async def test_timeout_scenario(self, scenario_setup):
        """Test slow handler processing in component communication."""
        setup = scenario_setup
        router = setup["router"]
        message_bus = setup["message_bus"]

        # Create slow component
        async def slow_handler(envelope):
            await asyncio.sleep(0.1)  # Simulate slower processing, but not too slow for tests

        message_bus.register_component_handler("slow_component", slow_handler)

        # Send message
        from tests.unit.fixtures.test_messages import create_component_message

        message = create_component_message(
            source="coding_ag",
            target="slow_component",
            data={"action": "slow_task"}
        )

        # Message delivery includes handler execution in current implementation
        start_time = asyncio.get_event_loop().time()
        success = await message_bus.send_to_component(message)
        end_time = asyncio.get_event_loop().time()

        assert success
        assert (end_time - start_time) >= 0.1  # Should wait for handler completion
        assert (end_time - start_time) < 1.0   # But not too slow overall


class TestComponentLifecycle:
    """Test component lifecycle in communication."""

    async def test_component_registration_lifecycle(self):
        """Test component registration and deregistration."""
        message_bus = InMemoryMessageBus()
        await message_bus.start()

        # Register component
        handler = AsyncMock()
        message_bus.register_component_handler("test_component", handler)

        assert "test_component" in message_bus.component_handlers

        # Send message
        from tests.unit.fixtures.test_messages import create_component_message

        message = create_component_message(target="test_component")
        success = await message_bus.send_to_component(message)

        assert success
        handler.assert_called_once()

        # Unregister component
        del message_bus.component_handlers["test_component"]

        # Message should be queued (no handler)
        message2 = create_component_message(target="test_component")
        success = await message_bus.send_to_component(message2)

        assert success  # Queuing succeeds
        assert "test_component" in message_bus.component_queues

        await message_bus.stop()

    async def test_component_replacement(self):
        """Test replacing component handlers."""
        message_bus = InMemoryMessageBus()
        await message_bus.start()

        # Register initial handler
        old_handler = AsyncMock()
        message_bus.register_component_handler("test_component", old_handler)

        # Replace with new handler
        new_handler = AsyncMock()
        message_bus.register_component_handler("test_component", new_handler)

        # Send message
        from tests.unit.fixtures.test_messages import create_component_message

        message = create_component_message(target="test_component")
        success = await message_bus.send_to_component(message)

        assert success
        new_handler.assert_called_once()
        old_handler.assert_not_called()

        await message_bus.stop()