#!/usr/bin/env python3
"""
Test the real-time event streaming fix.
"""

import asyncio
import sys
import time
import threading
from pathlib import Path
from unittest.mock import AsyncMock

# Add woodwork to path
sys.path.insert(0, str(Path(__file__).parent))


async def test_real_time_fix():
    """Test the real-time event streaming fix."""
    print("🔍 Testing Real-Time Event Streaming Fix")
    print("=" * 50)

    try:
        from woodwork.components.inputs.api_input import api_input, WebSocketSession
        from woodwork.events import emit

        # Create API input component
        api_component = api_input(name="input", to=["coding_ag"], local=False)

        # Mock WebSocket session with mock uvicorn loop
        mock_websocket = AsyncMock()
        session = WebSocketSession(
            websocket=mock_websocket,
            session_id="test_session",
            subscribed_components=["*"],
            created_at=time.time()
        )
        api_component._websocket_sessions["test_session"] = session

        # Mock the uvicorn loop for real-time messaging
        api_component._uvicorn_loop = asyncio.get_event_loop()

        # Start cross-thread processor
        processor_task = asyncio.create_task(api_component._cross_thread_event_processor())

        print(f"✅ Setup complete - testing real-time delivery")

        # Test 1: Real-time events should use immediate delivery
        print(f"\n1️⃣ Testing immediate delivery for real-time events...")

        real_time_events = [
            ("agent.thought", {"thought": "Real-time thought", "component_id": "coding_ag"}),
            ("agent.action", {"action": {"tool": "test", "inputs": {}}, "component_id": "coding_ag"}),
            ("tool.call", {"tool": "test_tool", "args": {}, "component_id": "coding_ag"}),
        ]

        received_count = 0
        for event_type, payload in real_time_events:
            mock_websocket.send_json.reset_mock()

            print(f"   Emitting {event_type}...")
            emit(event_type, payload)

            # Very small delay
            await asyncio.sleep(0.01)

            if mock_websocket.send_json.called:
                received_count += 1
                print(f"   ✅ Received {event_type} immediately")
            else:
                print(f"   ❌ {event_type} not received immediately")

        print(f"   📊 Immediate delivery: {received_count}/{len(real_time_events)} events")

        # Test 2: Cross-thread real-time events
        print(f"\n2️⃣ Testing cross-thread real-time events...")

        def emit_from_thread():
            thread_name = threading.current_thread().name
            print(f"   📡 Emitting from thread: {thread_name}")

            emit("agent.thought", {
                "thought": f"Cross-thread real-time thought from {thread_name}",
                "component_id": "coding_ag"
            })

        mock_websocket.send_json.reset_mock()

        # Emit from different thread
        thread = threading.Thread(target=emit_from_thread, name="TestLLMThread")
        thread.start()
        thread.join()

        # Small delay for processing
        await asyncio.sleep(0.1)

        if mock_websocket.send_json.called:
            print(f"   ✅ Cross-thread real-time event delivered")
        else:
            print(f"   ❌ Cross-thread real-time event not delivered")

        # Test 3: Non-real-time events should still use queue
        print(f"\n3️⃣ Testing non-real-time events use queue...")

        mock_websocket.send_json.reset_mock()

        emit("workflow.started", {"workflow": "test", "component_id": "coding_ag"})

        # Very small delay
        await asyncio.sleep(0.01)

        immediate_delivery = mock_websocket.send_json.called
        print(f"   Non-real-time immediate delivery: {'✅ YES' if immediate_delivery else '❌ NO'}")

        # Wait for queue processing
        await asyncio.sleep(0.2)

        queue_delivery = mock_websocket.send_json.called
        print(f"   Queue delivery: {'✅ YES' if queue_delivery else '❌ NO'}")

        # Cleanup
        processor_task.cancel()
        try:
            await processor_task
        except asyncio.CancelledError:
            pass

        # Summary
        print(f"\n📊 Test Results:")
        print(f"   Real-time immediate delivery: {received_count}/{len(real_time_events)}")
        print(f"   Cross-thread delivery: {'✅' if mock_websocket.send_json.called else '❌'}")
        print(f"   Non-real-time queuing: {'✅' if queue_delivery else '❌'}")

        return received_count >= 2  # At least 2 real-time events delivered immediately

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    success = await test_real_time_fix()

    if success:
        print(f"\n✅ Real-time fix test completed successfully")
        print(f"Your WebSocket should now receive events as they happen!")
    else:
        print(f"\n❌ Real-time fix test failed")


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)