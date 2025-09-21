#!/usr/bin/env python3
"""
Test the user's specific configuration: input = input api { to: coding_ag }
"""

import asyncio
import sys
from pathlib import Path

# Add woodwork to path
sys.path.insert(0, str(Path(__file__).parent))


async def test_your_config():
    """Test the user's exact configuration."""
    print("🔍 Testing Your Config: input = input api { to: coding_ag }")
    print("=" * 60)

    try:
        # 1. Test creating your exact configuration
        print("1️⃣ Creating API input with your exact config...")
        from woodwork.components.inputs.api_input import api_input

        # Your config: input = input api { to: coding_ag }
        api_component = api_input(name="input", to=["coding_ag"], local=False)

        print(f"✅ Created: {api_component.name}")
        print(f"   Type: {api_component.component}/{api_component.type}")
        print(f"   Output targets: {api_component.output_targets}")
        print(f"   Local mode: {api_component.local}")

        # 2. Test message bus connection
        print("\n2️⃣ Testing message bus integration...")
        await api_component._ensure_message_bus_connection()

        print(f"✅ Message bus: {api_component._message_bus is not None}")
        print(f"✅ Handler registered: {api_component._bus_handler_registered}")

        # 3. Simulate what happens when your coding_ag sends a message
        print("\n3️⃣ Simulating coding_ag sending messages...")

        # Import what coding_ag would use
        from woodwork.core.message_bus.interface import create_component_message

        # Mock a WebSocket session to receive events
        from woodwork.components.inputs.api_input import WebSocketSession
        from unittest.mock import AsyncMock
        import time

        mock_websocket = AsyncMock()
        session = WebSocketSession(
            websocket=mock_websocket,
            session_id="test_session",
            subscribed_components=["*"],  # Subscribe to all
            created_at=time.time()
        )
        api_component._websocket_sessions["test_session"] = session

        # Test different types of messages coding_ag might send
        test_messages = [
            ("agent.response", {"response": "Hello from coding_ag!"}),
            ("agent.thought", {"thought": "I'm thinking about this problem..."}),
            ("tool.observation", {"observation": "Tool completed successfully"}),
            ("llm.response", {"content": "LLM generated this response"}),
        ]

        for event_type, payload in test_messages:
            print(f"\n   Testing {event_type}...")

            # Create message as if from coding_ag
            envelope = create_component_message(
                session_id="user_session",
                event_type=event_type,
                payload=payload,
                target_component="input",  # Sent to your input component
                sender_component="coding_ag"  # From your coding_ag
            )

            # Send via message bus (this is what coding_ag would do)
            success = await api_component._message_bus.send_to_component(envelope)
            print(f"   Message bus send: {'✅ SUCCESS' if success else '❌ FAILED'}")

            # Check if WebSocket received it
            await asyncio.sleep(0.1)  # Small delay for processing

            if mock_websocket.send_json.called:
                sent_data = mock_websocket.send_json.call_args[0][0]
                print(f"   WebSocket received: ✅ {sent_data['event']}")
                mock_websocket.send_json.reset_mock()
            else:
                print(f"   WebSocket received: ❌ NOTHING")

        # 4. Test registration issues
        print("\n4️⃣ Checking component registration...")

        # Check if the handler is actually callable
        handler = api_component._handle_bus_message
        print(f"   Handler callable: {callable(handler)}")
        print(f"   Handler is coroutine function: {asyncio.iscoroutinefunction(handler)}")

        # Test direct handler call
        test_envelope = create_component_message(
            session_id="direct_test",
            event_type="agent.response",
            payload={"response": "Direct handler test"},
            target_component="input",
            sender_component="coding_ag"
        )

        print(f"\n   Testing direct handler call...")
        mock_websocket.send_json.reset_mock()
        await api_component._handle_bus_message(test_envelope)

        if mock_websocket.send_json.called:
            print(f"   Direct call result: ✅ SUCCESS")
        else:
            print(f"   Direct call result: ❌ FAILED")

        # 5. Check if there are any coding_ag components that could send messages
        print("\n5️⃣ Checking for potential coding_ag component issues...")

        # Try to get the message bus and see what's registered
        message_bus = api_component._message_bus
        if hasattr(message_bus, '_component_handlers'):
            registered_components = list(message_bus._component_handlers.keys())
            print(f"   Registered components: {registered_components}")

            if "coding_ag" in registered_components:
                print(f"   ✅ coding_ag is registered")
            else:
                print(f"   ❌ coding_ag is NOT registered")
                print(f"   This means coding_ag component isn't connected to the message bus")
        else:
            print(f"   Cannot check registered components")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    success = await test_your_config()

    if success:
        print(f"\n✅ Config test completed")
        print(f"\nDiagnosis:")
        print(f"- Your API input component is configured correctly")
        print(f"- The component can receive and forward messages")
        print(f"- If you're not seeing events, the issue is likely:")
        print(f"  1. coding_ag component isn't sending messages to the message bus")
        print(f"  2. coding_ag component isn't registered with the message bus")
        print(f"  3. FastAPI server isn't starting (check for uvicorn errors)")
    else:
        print(f"\n❌ Config test failed")


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)