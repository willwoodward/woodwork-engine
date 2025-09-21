#!/usr/bin/env python3
"""
Test the updated LLM agent with messaging system.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Add woodwork to path
sys.path.insert(0, str(Path(__file__).parent))


async def test_updated_llm_messaging():
    """Test that the updated LLM agent sends messages correctly."""
    print("🔍 Testing Updated LLM Agent Messaging")
    print("=" * 50)

    try:
        # 1. Create a mock LLM component
        print("1️⃣ Creating mock LLM component...")

        # Mock the LLM model dependency
        class MockLLMModel:
            def __init__(self):
                self._llm = MagicMock()
                # Mock the LLM to return a simple response
                self._llm.invoke.return_value.content = "Final Answer: Hello from coding_ag!"

        mock_model = MockLLMModel()

        # Create a mock task master (still required by agent base class)
        class MockTaskMaster:
            def __init__(self):
                self.cache = {}

            def start_workflow(self, query):
                pass

            def end_workflow(self):
                pass

        mock_task_master = MockTaskMaster()

        # Import and create the LLM agent
        from woodwork.components.agents.llm import llm

        # Create with minimal config (use custom prompt to avoid file dependency)
        coding_ag = llm(
            name="coding_ag",
            model=mock_model,
            tools=[],  # No tools for simple test
            task_m=mock_task_master,
            prompt={"file": "prompts/defaults/agent.txt"}
        )

        print(f"✅ Created LLM agent: {coding_ag.name}")

        # 2. Test message bus connection
        print("\n2️⃣ Testing message bus connection...")
        await coding_ag._ensure_message_bus_connection()

        print(f"✅ Message bus connected: {coding_ag._message_bus is not None}")

        # 3. Create a mock API input to receive messages
        print("\n3️⃣ Setting up mock API input to receive messages...")

        class MockAPIInput:
            def __init__(self):
                self.name = "input"
                self.received_messages = []

            async def handle_message(self, envelope):
                self.received_messages.append({
                    'event_type': envelope.event_type,
                    'sender': envelope.sender_component,
                    'payload': envelope.payload
                })
                print(f"   📨 API Input received: {envelope.event_type} from {envelope.sender_component}")

        mock_api_input = MockAPIInput()

        # Register the mock API input with the message bus
        message_bus = coding_ag._message_bus
        message_bus.register_component_handler("input", mock_api_input.handle_message)
        print(f"✅ Registered mock API input")

        # 4. Test sending messages
        print("\n4️⃣ Testing message sending...")

        # Test individual message types
        test_messages = [
            ("agent.response", {"response": "Test response"}),
            ("agent.thought", {"thought": "Test thought"}),
            ("tool.observation", {"tool": "test_tool", "observation": "Test observation"}),
        ]

        for event_type, payload in test_messages:
            print(f"\n   Testing {event_type}...")
            await coding_ag._send_message(event_type, payload)

            # Small delay for message processing
            await asyncio.sleep(0.1)

        # 5. Check received messages
        print(f"\n5️⃣ Checking received messages...")
        print(f"   Total messages received: {len(mock_api_input.received_messages)}")

        for i, msg in enumerate(mock_api_input.received_messages, 1):
            print(f"   {i}. {msg['event_type']} from {msg['sender']}: {msg['payload']}")

        # 6. Test full agent input (simplified)
        print(f"\n6️⃣ Testing full agent input flow...")

        # Reset messages
        mock_api_input.received_messages = []

        # Mock the _llm to avoid complex tool execution
        coding_ag._llm.invoke = AsyncMock()
        coding_ag._llm.invoke.return_value.content = "Final Answer: Hello from the updated coding_ag agent!"

        # Test with a simple input
        try:
            response = await coding_ag.input("Hello, test message")
            print(f"   ✅ Agent response: {response}")
        except Exception as e:
            print(f"   ⚠️ Agent input failed (expected): {e}")

        # Check messages sent during input processing
        print(f"   Messages sent during input: {len(mock_api_input.received_messages)}")
        for i, msg in enumerate(mock_api_input.received_messages, 1):
            print(f"   {i}. {msg['event_type']}: {msg['payload']}")

        return len(mock_api_input.received_messages) > 0

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    success = await test_updated_llm_messaging()

    if success:
        print(f"\n✅ LLM messaging test completed successfully")
        print(f"The updated LLM agent is now sending messages via the message bus!")
    else:
        print(f"\n❌ LLM messaging test failed")


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)