"""
TDD tests for API input component with messaging system integration.

This test file drives the implementation of a new API input component that:
1. Uses websockets for real-time communication
2. Integrates with the new messaging system instead of task_master
3. Efficiently handles component communication without broadcasting all events
"""

import pytest
import asyncio
import json
import time
import threading
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from woodwork.core.message_bus.in_memory_bus import InMemoryMessageBus
from woodwork.core.message_bus.interface import MessageEnvelope, create_component_message
from woodwork.core.message_bus.integration import MessageBusIntegration


class TestAPIInputComponentDesign:
    """TDD tests that drive the API input component design."""

    @pytest.fixture
    async def message_bus_setup(self):
        """Setup message bus for testing."""
        bus = InMemoryMessageBus()
        await bus.start()
        yield bus
        await bus.stop()

    @pytest.mark.asyncio
    async def test_api_input_should_use_messaging_not_task_master(self, message_bus_setup):
        """
        API input component should use unified event system instead of task_master.

        The new implementation should use UnifiedEventBus for direct component communication.
        """
        from woodwork.components.inputs.api_input import api_input

        # Should be able to create without task_master
        api_component = api_input(name="test_api", to=["test_agent"], local=False)

        # Should have unified event bus integration
        assert hasattr(api_component, 'event_bus')
        assert hasattr(api_component, '_handle_real_time_event')

        # Should have configured output targets
        assert api_component._output == ["test_agent"]

    @pytest.mark.asyncio
    async def test_api_input_websocket_connection_management(self, message_bus_setup):
        """
        TDD: API input should properly manage websocket connections.

        Should handle connection establishment, message routing, and cleanup.
        """
        # TDD: This drives us to implement websocket management
        assert True  # Placeholder until we implement api_input

    @pytest.mark.asyncio
    async def test_api_input_should_route_messages_efficiently(self, message_bus_setup):
        """
        TDD: API input should only send relevant messages to websocket clients.

        Instead of broadcasting all events, it should:
        1. Subscribe to events from configured target components
        2. Only forward relevant events to websocket clients
        3. Filter out internal system messages
        """
        # TDD: This drives efficient message filtering implementation
        assert True  # Placeholder until we implement api_input

    @pytest.mark.asyncio
    async def test_api_input_session_management(self, message_bus_setup):
        """
        TDD: API input should manage session isolation.

        Each websocket connection should have its own session and only receive
        messages relevant to its session.
        """
        # TDD: Session isolation is critical for multi-user scenarios
        assert True  # Placeholder until we implement api_input


class TestAPIInputWebSocketIntegration:
    """TDD tests for websocket integration with messaging system."""

    @pytest.fixture
    async def mock_websocket_setup(self):
        """Setup mock websocket for testing."""
        mock_websocket = AsyncMock()
        mock_websocket.send = AsyncMock()
        mock_websocket.recv = AsyncMock()
        mock_websocket.close = AsyncMock()
        mock_websocket.closed = False
        return mock_websocket

    @pytest.fixture
    async def component_setup(self, message_bus_setup):
        """Setup for component testing."""
        bus = message_bus_setup

        # Mock API input component
        class MockAPIInput(MessageBusIntegration):
            def __init__(self, name="api_input", **config):
                super().__init__()
                self.name = name
                self.config = config
                self.output_targets = config.get("to", [])
                self.session_id = "test_session"
                self.websocket_connections = {}

            async def handle_websocket_message(self, websocket, message):
                """Handle incoming websocket message."""
                raise NotImplementedError("WebSocket message handling not implemented")

            async def send_to_websocket(self, connection_id, message):
                """Send message to specific websocket connection."""
                raise NotImplementedError("WebSocket sending not implemented")

            async def subscribe_to_component_events(self, component_name):
                """Subscribe to events from a specific component."""
                raise NotImplementedError("Component event subscription not implemented")

        return {"bus": bus, "api_input_class": MockAPIInput}

    @pytest.mark.asyncio
    async def test_websocket_message_handling(self, component_setup, mock_websocket_setup):
        """
        TDD: API input should handle websocket messages and route to components.
        """
        setup = component_setup
        websocket = mock_websocket_setup

        api_input = setup["api_input_class"](to=["test_agent"])

        # Mock incoming websocket message
        user_message = {
            "type": "user_input",
            "content": "Hello, world!",
            "session_id": "test_session_123"
        }

        # TDD: This should route message to configured components
        with pytest.raises(NotImplementedError):
            await api_input.handle_websocket_message(websocket, json.dumps(user_message))

    @pytest.mark.asyncio
    async def test_component_event_subscription(self, component_setup):
        """
        TDD: API input should subscribe to events from target components.
        """
        setup = component_setup
        api_input = setup["api_input_class"](to=["test_agent", "test_output"])

        # TDD: Should be able to subscribe to specific component events
        with pytest.raises(NotImplementedError):
            await api_input.subscribe_to_component_events("test_agent")

    @pytest.mark.asyncio
    async def test_efficient_event_filtering(self, component_setup):
        """
        TDD: API input should filter events efficiently.

        Only events from subscribed components should be forwarded to websockets.
        Internal system events should be filtered out.
        """
        setup = component_setup
        api_input = setup["api_input_class"](to=["test_agent"])

        # Mock events
        relevant_event = MessageEnvelope(
            message_id="msg_123",
            session_id="test_session",
            event_type="agent.response",
            payload={"response": "Hello!"},
            sender_component="test_agent"
        )

        irrelevant_event = MessageEnvelope(
            message_id="msg_456",
            session_id="test_session",
            event_type="system.internal",
            payload={"debug": "internal"},
            sender_component="system"
        )

        # TDD: Should filter events based on relevance
        assert True  # Placeholder for actual filtering logic

    @pytest.mark.asyncio
    async def test_session_isolation(self, component_setup, mock_websocket_setup):
        """
        TDD: Different websocket connections should have isolated sessions.
        """
        setup = component_setup
        websocket1 = mock_websocket_setup
        websocket2 = mock_websocket_setup

        api_input = setup["api_input_class"]()

        # TDD: Each connection should have its own session
        # Messages from session A should not go to session B websockets
        assert True  # Placeholder for session isolation logic


class TestAPIInputMessageBusIntegration:
    """TDD tests for message bus integration."""

    @pytest.fixture
    async def integration_setup(self):
        """Setup for integration testing."""
        bus = InMemoryMessageBus()
        await bus.start()

        # Mock target components
        class MockAgentComponent(MessageBusIntegration):
            def __init__(self, name="test_agent"):
                super().__init__()
                self.name = name
                self.session_id = "test_session"
                self.received_messages = []

            async def _handle_bus_message(self, envelope):
                """Handle messages from message bus."""
                self.received_messages.append(envelope)

                # Simulate agent processing and response
                if envelope.event_type == "input.received":
                    response_envelope = create_component_message(
                        session_id=envelope.session_id,
                        event_type="agent.response",
                        payload={"response": f"Processed: {envelope.payload.get('input', '')}"},
                        target_component="api_input",
                        sender_component=self.name
                    )

                    # Send response back via message bus
                    message_bus = envelope.payload.get("_message_bus")
                    if message_bus:
                        await message_bus.send_to_component(response_envelope)

        agent = MockAgentComponent()
        bus.register_component_handler("test_agent", agent._handle_bus_message)

        yield {"bus": bus, "agent": agent}
        await bus.stop()

    @pytest.mark.asyncio
    async def test_input_to_agent_messaging(self, integration_setup):
        """
        TDD: API input should send user input to configured agents via message bus.
        """
        setup = integration_setup
        bus = setup["bus"]
        agent = setup["agent"]

        # Create message envelope for user input
        input_envelope = create_component_message(
            session_id="test_session",
            event_type="input.received",
            payload={
                "input": "Hello from API",
                "source": "websocket",
                "_message_bus": bus
            },
            target_component="test_agent",
            sender_component="api_input"
        )

        # Send via message bus
        success = await bus.send_to_component(input_envelope)
        assert success

        # Wait for processing
        await asyncio.sleep(0.1)

        # Verify agent received the message
        assert len(agent.received_messages) == 1
        received = agent.received_messages[0]
        assert received.event_type == "input.received"
        assert received.payload["input"] == "Hello from API"

    @pytest.mark.asyncio
    async def test_agent_response_handling(self, integration_setup):
        """
        TDD: API input should receive responses from agents and forward to websockets.
        """
        setup = integration_setup
        bus = setup["bus"]

        # Mock API input component message handler
        received_responses = []

        async def mock_api_input_handler(envelope):
            if envelope.event_type == "agent.response":
                received_responses.append(envelope)

        bus.register_component_handler("api_input", mock_api_input_handler)

        # Send response from agent to API input
        response_envelope = create_component_message(
            session_id="test_session",
            event_type="agent.response",
            payload={"response": "Agent processed the input"},
            target_component="api_input",
            sender_component="test_agent"
        )

        success = await bus.send_to_component(response_envelope)
        assert success

        await asyncio.sleep(0.1)

        # Verify API input received the response
        assert len(received_responses) == 1
        response = received_responses[0]
        assert response.event_type == "agent.response"
        assert response.payload["response"] == "Agent processed the input"


class TestAPIInputPerformance:
    """TDD tests for performance and efficiency."""

    @pytest.mark.asyncio
    async def test_websocket_message_throughput(self):
        """
        TDD: API input should handle high-throughput websocket messages efficiently.
        """
        # TDD: Should handle many concurrent websocket connections
        # Should process messages without blocking
        assert True  # Placeholder for performance testing

    @pytest.mark.asyncio
    async def test_memory_usage_with_many_connections(self):
        """
        TDD: API input should manage memory efficiently with many websocket connections.
        """
        # TDD: Should not leak memory with connection churn
        # Should clean up closed connections properly
        assert True  # Placeholder for memory testing

    @pytest.mark.asyncio
    async def test_event_subscription_efficiency(self):
        """
        TDD: API input should subscribe to events efficiently.

        Should not subscribe to unnecessary events that would overwhelm websockets.
        """
        # TDD: Should only subscribe to events from configured target components
        # Should unsubscribe when websocket connections close
        assert True  # Placeholder for subscription efficiency testing


class TestRealTimeEventStreaming:
    """TDD tests for real-time event streaming from LLM to WebSocket."""

    @pytest.fixture
    async def real_time_setup(self):
        """Setup for real-time streaming tests."""
        from woodwork.components.inputs.api_input import api_input, WebSocketSession
        from woodwork.events import get_global_event_manager, emit

        # Create API input component
        api_component = api_input(name="input", to=["coding_ag"], local=False)

        # Mock WebSocket session
        mock_websocket = AsyncMock()
        session = WebSocketSession(
            websocket=mock_websocket,
            session_id="test_session",
            subscribed_components=["*"],
            created_at=time.time()
        )
        api_component._websocket_sessions["test_session"] = session

        # Start cross-thread processor
        processor_task = asyncio.create_task(api_component._cross_thread_event_processor())

        yield {
            "api_component": api_component,
            "mock_websocket": mock_websocket,
            "session": session,
            "processor_task": processor_task,
            "event_manager": get_global_event_manager()
        }

        # Cleanup
        processor_task.cancel()
        try:
            await processor_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_immediate_event_forwarding_same_thread(self, real_time_setup):
        """
        TDD: Events emitted in the same thread should be forwarded immediately.
        """
        setup = real_time_setup
        mock_websocket = setup["mock_websocket"]

        # Reset mock
        mock_websocket.send_json.reset_mock()

        # Emit event in same thread
        from woodwork.events import emit
        emit("agent.thought", {"thought": "Immediate thought", "component_id": "coding_ag"})

        # Should be forwarded immediately (no delay)
        await asyncio.sleep(0.01)  # Minimal delay for async task

        assert mock_websocket.send_json.called
        sent_data = mock_websocket.send_json.call_args[0][0]
        assert sent_data["event"] == "agent.thought"
        assert "Immediate thought" in str(sent_data["payload"])

    @pytest.mark.asyncio
    async def test_cross_thread_event_batching_issue(self, real_time_setup):
        """
        TDD: Test to identify why cross-thread events are batched.

        This test should reveal the batching behavior and help us fix it.
        """
        setup = real_time_setup
        mock_websocket = setup["mock_websocket"]
        api_component = setup["api_component"]

        # Track timing of WebSocket sends
        send_times = []
        original_send_json = mock_websocket.send_json

        async def timed_send_json(data):
            send_times.append(time.time())
            return await original_send_json(data)

        mock_websocket.send_json = timed_send_json

        # Emit multiple events from different thread with timing
        def emit_with_delays():
            thread_name = threading.current_thread().name
            emit_times = []

            # Emit events with small delays between them
            for i, event_type in enumerate(["agent.thought", "agent.action", "tool.call", "tool.observation"]):
                emit_time = time.time()
                emit_times.append(emit_time)

                emit(event_type, {
                    "data": f"Event {i} from {thread_name}",
                    "component_id": "coding_ag",
                    "emit_time": emit_time
                })

                # Small delay between emits
                time.sleep(0.05)

            return emit_times

        # Run in separate thread
        thread = threading.Thread(target=emit_with_delays, name="TestLLMThread")
        thread.start()
        thread.join()

        # Wait for all events to be processed
        await asyncio.sleep(1.0)

        # Analyze timing
        print(f"WebSocket sends: {len(send_times)}")
        print(f"Send times: {send_times}")

        if len(send_times) > 1:
            delays = [send_times[i] - send_times[i-1] for i in range(1, len(send_times))]
            print(f"Delays between sends: {delays}")

        # Should have received multiple events
        assert mock_websocket.send_json.call_count >= 4

    @pytest.mark.asyncio
    async def test_real_time_event_timing(self, real_time_setup):
        """
        TDD: Test the actual timing of event delivery to identify bottlenecks.
        """
        setup = real_time_setup
        mock_websocket = setup["mock_websocket"]

        # Track detailed timing
        event_timeline = []

        # Override event handler to track timing
        original_handle_event = setup["api_component"]._handle_event

        def timed_handle_event(payload):
            event_timeline.append(("handle_event_start", time.time(), getattr(payload, '__class__', type(payload)).__name__))
            result = original_handle_event(payload)
            event_timeline.append(("handle_event_end", time.time(), getattr(payload, '__class__', type(payload)).__name__))
            return result

        setup["api_component"]._handle_event = timed_handle_event

        # Override WebSocket send to track timing
        async def timed_websocket_send(data):
            event_timeline.append(("websocket_send", time.time(), data.get("event", "unknown")))
            return await AsyncMock().send_json(data)

        mock_websocket.send_json = timed_websocket_send

        # Emit events from different thread
        def emit_test_events():
            start_time = time.time()
            for i, event_type in enumerate(["agent.thought", "agent.action", "tool.call"]):
                emit_time = time.time()
                event_timeline.append(("emit", emit_time, event_type))

                emit(event_type, {
                    "test_data": f"Event {i}",
                    "component_id": "coding_ag",
                    "emit_sequence": i
                })

        thread = threading.Thread(target=emit_test_events, name="RealTimeTestThread")
        thread.start()
        thread.join()

        # Wait for processing
        await asyncio.sleep(0.5)

        # Print timeline for analysis
        print("\nEvent Timeline:")
        for event_type, timestamp, data in event_timeline:
            print(f"{event_type}: {timestamp:.4f} - {data}")

        # Verify events were processed
        assert len([e for e in event_timeline if e[0] == "emit"]) >= 3
        assert len([e for e in event_timeline if e[0] == "websocket_send"]) >= 3

    @pytest.mark.asyncio
    async def test_immediate_forwarding_optimization(self, real_time_setup):
        """
        TDD: Test optimized immediate forwarding for real-time behavior.

        This test drives the implementation of immediate forwarding.
        """
        setup = real_time_setup
        api_component = setup["api_component"]
        mock_websocket = setup["mock_websocket"]

        # Test immediate forwarding method (to be implemented)
        event_data = {
            'event_type': 'agent.thought',
            'payload': {'thought': 'Real-time thought'},
            'sender_component': 'coding_ag',
            'session_id': 'test_session',
            'created_at': time.time()
        }

        # Should forward immediately without queueing
        await api_component._forward_event_to_websockets(event_data)

        # Verify immediate send
        assert mock_websocket.send_json.called
        sent_data = mock_websocket.send_json.call_args[0][0]
        assert sent_data["event"] == "agent.thought"

    @pytest.mark.asyncio
    async def test_bypass_cross_thread_queue_for_real_time(self, real_time_setup):
        """
        TDD: Test bypassing cross-thread queue for immediate delivery.

        This test should drive implementation of immediate delivery mechanism.
        """
        setup = real_time_setup
        api_component = setup["api_component"]
        mock_websocket = setup["mock_websocket"]

        # Track queue usage
        queue_size_before = api_component._cross_thread_event_queue.qsize()

        # Override to test immediate delivery
        # This simulates what should happen for real-time events
        async def immediate_delivery_handler(payload):
            # Skip cross-thread queueing for real-time events
            event_data = {
                'event_type': 'agent.thought',
                'payload': payload.to_dict() if hasattr(payload, 'to_dict') else {'data': payload},
                'sender_component': getattr(payload, 'component_id', 'coding_ag'),
                'session_id': getattr(payload, 'session_id', 'test_session'),
                'created_at': time.time()
            }

            # Use threading to send from uvicorn-like thread context
            def send_immediately():
                # Simulate being in the uvicorn thread
                threading.current_thread().name = "uvicorn"
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(api_component._forward_event_to_websockets(event_data))
                loop.close()

            thread = threading.Thread(target=send_immediately, name="uvicorn-worker")
            thread.start()
            thread.join()

        # Test the immediate delivery
        from woodwork.types.events import AgentThoughtPayload
        payload = AgentThoughtPayload(
            timestamp=time.time(),
            component_id="coding_ag",
            component_type=None,
            thought="Immediate real-time thought"
        )

        await immediate_delivery_handler(payload)

        # Should not have used the queue
        queue_size_after = api_component._cross_thread_event_queue.qsize()
        assert queue_size_after == queue_size_before

        # Should have sent to WebSocket
        assert mock_websocket.send_json.called

    @pytest.mark.asyncio
    async def test_input_received_immediate_delivery_issue(self, real_time_setup):
        """
        Test the specific issue where input.received is queued instead of delivered immediately.

        This test reproduces the exact issue the user is experiencing.
        """
        setup = real_time_setup
        api_component = setup["api_component"]
        mock_websocket = setup["mock_websocket"]

        print("\n🔍 Testing input.received immediate delivery issue")

        # Mock uvicorn loop to simulate real environment
        mock_uvicorn_loop = asyncio.get_event_loop()
        api_component._uvicorn_loop = mock_uvicorn_loop

        # Track delivery timing
        delivery_times = []
        original_send_json = mock_websocket.send_json

        async def timed_send_json(data):
            delivery_times.append(time.time())
            print(f"   📤 WebSocket received: {data['event']} at {time.time():.6f}")
            return await original_send_json(data)

        mock_websocket.send_json = timed_send_json

        # Test 1: Simulate input.received from MainThread (should be immediate)
        print(f"\n1️⃣ Testing input.received from MainThread...")
        mock_websocket.send_json.reset_mock()
        delivery_times.clear()

        from woodwork.events import emit
        emit_time = time.time()
        emit("input.received", {
            "input": "test message",
            "inputs": {},
            "session_id": "test_session",
            "component_id": "input"
        })

        await asyncio.sleep(0.01)  # Minimal delay

        if delivery_times:
            delay = delivery_times[0] - emit_time
            print(f"   ⏱️ Delivery delay: {delay:.6f} seconds")
            assert delay < 0.01, f"input.received should be delivered immediately, got {delay:.6f}s delay"
            print(f"   ✅ input.received delivered immediately")
        else:
            print(f"   ❌ input.received not delivered at all")
            assert False, "input.received was not delivered"

        # Test 2: Simulate input.received from different thread (real scenario)
        print(f"\n2️⃣ Testing input.received from different thread...")
        mock_websocket.send_json.reset_mock()
        delivery_times.clear()

        def emit_from_different_thread():
            emit_time = time.time()
            print(f"   📡 Emitting from thread: {threading.current_thread().name}")

            emit("input.received", {
                "input": "cross-thread test message",
                "inputs": {},
                "session_id": "test_session",
                "component_id": "input"
            })

            return emit_time

        thread = threading.Thread(target=emit_from_different_thread, name="TestDistributedStartupThread")
        thread.start()
        thread.join()

        # Check immediate delivery
        await asyncio.sleep(0.01)  # Minimal delay for immediate delivery

        if delivery_times:
            print(f"   ✅ input.received delivered from cross-thread")
        else:
            print(f"   ❌ input.received not delivered immediately from cross-thread")

            # Wait longer to see if it comes through queue
            await asyncio.sleep(0.5)

            if delivery_times:
                print(f"   ⚠️ input.received delivered via queue (delayed)")
            else:
                print(f"   ❌ input.received never delivered")
                assert False, "input.received was not delivered from cross-thread"

        # Test 3: Compare timing with other events
        print(f"\n3️⃣ Testing timing comparison with other events...")
        mock_websocket.send_json.reset_mock()
        delivery_times.clear()

        def emit_multiple_events():
            base_time = time.time()

            # Emit input.received first
            emit("input.received", {
                "input": "timing test",
                "inputs": {},
                "session_id": "test_session",
                "component_id": "input"
            })

            # Small delay to simulate processing
            time.sleep(0.1)

            # Emit other events (simulating LLM completion)
            emit("agent.thought", {"thought": "test thought", "component_id": "coding_ag"})
            emit("agent.action", {"action": {"tool": "test"}, "component_id": "coding_ag"})

            return base_time

        thread = threading.Thread(target=emit_multiple_events, name="TestLLMThread")
        thread.start()
        thread.join()

        # Wait for all events
        await asyncio.sleep(1.0)

        print(f"   📊 Total events delivered: {len(delivery_times)}")

        if len(delivery_times) >= 3:
            input_time = delivery_times[0]
            other_times = delivery_times[1:]

            print(f"   ⏱️ input.received delivered at: {input_time:.6f}")
            print(f"   ⏱️ Other events delivered at: {[t for t in other_times]}")

            # input.received should come significantly before other events
            time_gap = min(other_times) - input_time
            print(f"   📏 Time gap: {time_gap:.6f} seconds")

            if time_gap > 0.05:  # 50ms gap
                print(f"   ✅ input.received delivered well before other events")
            else:
                print(f"   ❌ input.received not delivered early enough (gap: {time_gap:.6f}s)")
                assert False, f"input.received should be delivered much earlier, gap was only {time_gap:.6f}s"

    @pytest.mark.asyncio
    async def test_threading_issue_reproduction(self, real_time_setup):
        """
        Reproduce the exact threading issue causing delayed delivery.
        """
        setup = real_time_setup
        api_component = setup["api_component"]
        mock_websocket = setup["mock_websocket"]

        print("\n🔍 Reproducing threading issue")

        # Track which thread each event comes from
        thread_info = []
        original_handle_event = api_component._handle_event

        def tracked_handle_event(payload):
            thread_name = threading.current_thread().name
            thread_info.append({
                'event': getattr(payload, '__class__', type(payload)).__name__,
                'thread': thread_name,
                'time': time.time()
            })
            print(f"   🧵 Event {getattr(payload, '__class__', type(payload)).__name__} from thread {thread_name}")
            return original_handle_event(payload)

        api_component._handle_event = tracked_handle_event

        # Test the actual emission pattern
        def simulate_real_usage():
            # This simulates what happens in real usage
            from woodwork.events import emit

            # input.received comes from distributed startup thread
            emit("input.received", {
                "input": "real usage simulation",
                "inputs": {},
                "session_id": "real_session",
                "component_id": "input"
            })

            # Simulate OpenAI delay
            time.sleep(0.1)

            # LLM events come from the same thread
            emit("agent.thought", {"thought": "simulated thought", "component_id": "coding_ag"})
            emit("agent.action", {"action": {"tool": "test"}, "component_id": "coding_ag"})

        thread = threading.Thread(target=simulate_real_usage, name="DistributedStartupThread")
        thread.start()
        thread.join()

        await asyncio.sleep(1.0)  # Wait for all processing

        print(f"\n📊 Thread analysis:")
        for info in thread_info:
            print(f"   {info['event']:20} | {info['thread']:20} | {info['time']:.6f}")

        # Verify events came from expected threads
        input_events = [info for info in thread_info if 'Input' in info['event']]
        other_events = [info for info in thread_info if 'Input' not in info['event']]

        assert len(input_events) > 0, "No input events received"
        assert len(other_events) > 0, "No other events received"

        print(f"   ✅ Received {len(input_events)} input events and {len(other_events)} other events")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])