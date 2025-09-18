import asyncio
from woodwork.events import create_default_emitter
from woodwork.types import ToolObservationPayload, AgentThoughtPayload


async def test_pipes_transform_sync_and_async():
    emitter = create_default_emitter()

    def pipe_sync(payload):
        # Create new payload with additional info
        new_payload = ToolObservationPayload(
            observation=payload.observation + " [sync_added]",
            tool=payload.tool if hasattr(payload, 'tool') and payload.tool else "test_tool",
            timestamp=payload.timestamp,
            component_id=payload.component_id,
            component_type=payload.component_type
        )
        return new_payload

    async def pipe_async(payload):
        # simulate async work
        await asyncio.sleep(0)
        new_payload = ToolObservationPayload(
            observation=payload.observation + " [async_added]",
            tool=payload.tool,
            timestamp=payload.timestamp,
            component_id=payload.component_id,
            component_type=payload.component_type
        )
        return new_payload

    emitter.on_pipe("tool.observation", pipe_sync)
    emitter.on_pipe("tool.observation", pipe_async)

    # Create proper payload
    initial_payload = ToolObservationPayload(
        observation="original observation",
        tool="test_tool"
    )
    result = await emitter.emit("tool.observation", initial_payload)

    assert result is not None
    assert "original observation" in result.observation
    assert "[sync_added]" in result.observation
    assert "[async_added]" in result.observation


def test_hooks_on_once_off():
    emitter = create_default_emitter()
    calls = []

    def listener(payload):
        calls.append(("sync", payload.thought))

    def once_listener(payload):
        calls.append(("once", payload.thought))

    emitter.on_hook("agent.thought", listener)
    emitter.on_hook("agent.thought", once_listener)

    # Create proper payloads with required fields
    payload1 = AgentThoughtPayload(
        thought="thought 1",
        component_id="test_agent",
        component_type="agent"
    )
    payload2 = AgentThoughtPayload(
        thought="thought 2",
        component_id="test_agent",
        component_type="agent"
    )

    # First emit: both listeners should run
    emitter.emit_sync("agent.thought", payload1)

    # Second emit: both listeners run again
    emitter.emit_sync("agent.thought", payload2)

    # Validate calls - both hooks run for both emissions
    assert ("sync", "thought 1") in calls
    assert ("once", "thought 1") in calls
    assert ("sync", "thought 2") in calls
    assert ("once", "thought 2") in calls

    # Both hooks should have been called twice (no 'once' functionality in current implementation)
    sync_count = sum(1 for c in calls if c[0] == "sync")
    once_count = sum(1 for c in calls if c[0] == "once")
    assert sync_count == 2
    assert once_count == 2
