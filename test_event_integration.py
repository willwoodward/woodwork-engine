#!/usr/bin/env python3
"""
Test the API input component with event system integration.
"""

import asyncio
import sys
from pathlib import Path

# Add woodwork to path
sys.path.insert(0, str(Path(__file__).parent))


async def test_event_integration():
    """Test that the API input component receives events from the LLM via event system."""
    print("🔍 Testing API Input Event System Integration")
    print("=" * 60)

    try:
        # 1. Test event system basics
        print("1️⃣ Testing event system basics...")

        from woodwork.events import emit, get_global_event_manager

        # Test that we can emit events
        event_manager = get_global_event_manager()
        print(f"✅ Event manager: {type(event_manager).__name__}")

        # 2. Create API input component (should register hooks)
        print("\n2️⃣ Creating API input component...")

        from woodwork.components.inputs.api_input import api_input
        from woodwork.components.inputs.api_input import WebSocketSession
        from unittest.mock import AsyncMock
        import time

        # Create API input component
        api_component = api_input(name="input", to=["coding_ag"], local=False)
        print(f"✅ Created API input: {api_component.name}")
        print(f"   Event hooks registered: {api_component._event_hooks_registered}")

        # Start the cross-thread processor manually for testing
        processor_task = asyncio.create_task(api_component._cross_thread_event_processor())
        print(f"✅ Started cross-thread processor")

        # 3. Add a mock WebSocket session
        print("\n3️⃣ Setting up mock WebSocket session...")

        mock_websocket = AsyncMock()
        session = WebSocketSession(
            websocket=mock_websocket,
            session_id="test_session",
            subscribed_components=["*"],  # Subscribe to all
            created_at=time.time()
        )
        api_component._websocket_sessions["test_session"] = session
        print(f"✅ Added mock WebSocket session")

        # Track successful events
        successful_events = 0

        # 4. Test emitting events that the LLM would emit
        print("\n4️⃣ Testing event emission...")

        test_events = [
            ("agent.thought", {"thought": "Testing agent thought", "component_id": "coding_ag"}),
            ("agent.response", {"response": "Hello from coding_ag!", "component_id": "coding_ag"}),
            ("tool.observation", {"tool": "test_tool", "observation": "Tool completed", "component_id": "coding_ag"}),
            ("agent.step_complete", {"step": 1, "session_id": "test", "component_id": "coding_ag"}),
        ]

        for event_type, payload in test_events:
            print(f"\n   Emitting {event_type}...")
            mock_websocket.send_json.reset_mock()

            # Emit the event (this is what the LLM does)
            result = emit(event_type, payload)
            print(f"   Emit result: {result}")

            # Small delay for processing
            await asyncio.sleep(0.2)

            # Check if WebSocket received it
            if mock_websocket.send_json.called:
                sent_data = mock_websocket.send_json.call_args[0][0]
                print(f"   ✅ WebSocket received: {sent_data['event']} - {sent_data.get('payload', {}).get('thought') or sent_data.get('payload', {}).get('response') or 'data'}")
                successful_events += 1
            else:
                print(f"   ❌ WebSocket received nothing")

        # 5. Test cross-thread scenario
        print(f"\n5️⃣ Testing cross-thread scenario...")

        import threading

        def emit_from_thread():
            thread_name = threading.current_thread().name
            print(f"   📡 Emitting from thread: {thread_name}")

            result = emit("agent.response", {
                "response": f"Cross-thread message from {thread_name}",
                "component_id": "coding_ag"
            })
            print(f"   📡 Emit result: {result}")

        # Reset mock
        mock_websocket.send_json.reset_mock()

        # Emit from different thread
        thread = threading.Thread(target=emit_from_thread, name="TestWorkerThread")
        thread.start()
        thread.join()

        # Wait a bit for cross-thread processing
        await asyncio.sleep(0.5)

        if mock_websocket.send_json.called:
            sent_data = mock_websocket.send_json.call_args[0][0]
            print(f"   ✅ WebSocket received cross-thread: {sent_data['event']}")
            successful_events += 1
        else:
            print(f"   ❌ WebSocket did not receive cross-thread event")

        # Clean up
        processor_task.cancel()
        try:
            await processor_task
        except asyncio.CancelledError:
            pass

        print(f"\n📊 Summary: {successful_events} successful events out of 5 total")
        return successful_events >= 4  # At least 4 events successfully received

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    success = await test_event_integration()

    if success:
        print(f"\n✅ Event integration test completed successfully")
        print(f"The API input component is now receiving events from the LLM!")
    else:
        print(f"\n❌ Event integration test failed")


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)