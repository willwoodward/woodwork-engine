#!/usr/bin/env python3
"""
Test to understand when the LLM agent emits events and fix real-time emission.
"""

import asyncio
import sys
import time
from pathlib import Path

# Add woodwork to path
sys.path.insert(0, str(Path(__file__).parent))


async def test_llm_emission_timing():
    """Test when the LLM agent emits events."""
    print("🔍 Testing LLM Agent Event Emission Timing")
    print("=" * 50)

    try:
        # Track all event emissions with timestamps
        emission_log = []

        # Override the emit function to track timing
        from woodwork.events import events
        original_emit_sync = events.get_global_event_manager().emit_sync

        def timed_emit_sync(event, data=None):
            timestamp = time.time()
            emission_log.append((timestamp, event, data))
            print(f"📢 EMIT: {timestamp:.4f} - {event} - {type(data)}")
            return original_emit_sync(event, data)

        events.get_global_event_manager().emit_sync = timed_emit_sync

        # Create a simplified LLM agent to test timing
        from woodwork.components.agents.llm import llm
        from woodwork.components.llms.llm import llm as base_llm

        # Mock the underlying LLM to control when it responds
        class MockLLM:
            def __init__(self):
                self._llm = self

            def invoke(self, input_data):
                # Simulate thinking time
                print(f"🤔 LLM starting to think at {time.time():.4f}")
                time.sleep(0.1)  # Simulate processing time

                response_content = "Final Answer: Test response after thinking"
                print(f"💭 LLM finished thinking at {time.time():.4f}")

                # Mock response object
                class MockResponse:
                    def __init__(self, content):
                        self.content = content

                return MockResponse(response_content)

        # Create mock task master
        class MockTaskMaster:
            def __init__(self):
                self.cache = {}

            def start_workflow(self, query):
                print(f"🚀 Workflow started at {time.time():.4f}")

            def end_workflow(self):
                print(f"🏁 Workflow ended at {time.time():.4f}")

        mock_llm = MockLLM()
        mock_task_master = MockTaskMaster()

        # Create the LLM agent
        coding_ag = llm(
            name="coding_ag",
            model=mock_llm,
            tools=[],
            task_m=mock_task_master,
            prompt={"file": "prompts/defaults/agent.txt"}
        )

        print(f"\n⏰ Starting LLM input at {time.time():.4f}")
        start_time = time.time()

        # Call the LLM agent input method
        response = await coding_ag.input("Test message for timing analysis")

        end_time = time.time()
        print(f"⏰ LLM input completed at {end_time:.4f}")
        print(f"⏰ Total duration: {end_time - start_time:.4f} seconds")

        print(f"\n📊 Event Emission Analysis:")
        print(f"Total events emitted: {len(emission_log)}")

        if emission_log:
            # Calculate time differences
            first_emit = emission_log[0][0]
            last_emit = emission_log[-1][0]

            print(f"\nEvent Timeline:")
            for i, (timestamp, event, data) in enumerate(emission_log):
                relative_time = timestamp - start_time
                print(f"{i+1:2}. {relative_time:+6.3f}s: {event}")

            print(f"\nTiming Analysis:")
            print(f"First event: {first_emit - start_time:+6.3f}s after start")
            print(f"Last event:  {last_emit - start_time:+6.3f}s after start")
            print(f"Emission span: {last_emit - first_emit:.4f}s")

            # Check if events are bunched together
            if len(emission_log) > 1:
                delays = [emission_log[i][0] - emission_log[i-1][0] for i in range(1, len(emission_log))]
                avg_delay = sum(delays) / len(delays)
                print(f"Average delay between events: {avg_delay:.4f}s")

                if avg_delay < 0.001:  # Less than 1ms
                    print("🚨 ISSUE: Events are emitted in a tight batch (< 1ms apart)")
                    print("   This explains why WebSocket receives them all at once")
                else:
                    print("✅ Events are emitted with reasonable spacing")

        return len(emission_log) > 0

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    success = await test_llm_emission_timing()

    print(f"\n{'='*50}")
    if success:
        print("✅ LLM emission timing test completed")
        print("\nNext steps:")
        print("1. If events are bunched together, we need to modify the LLM to emit them during processing")
        print("2. If events are spaced out, the issue is in the WebSocket forwarding")
    else:
        print("❌ LLM emission timing test failed")


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)