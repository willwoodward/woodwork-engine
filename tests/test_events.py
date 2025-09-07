import asyncio
from woodwork.events import EventEmitter


def test_pipes_transform_sync_and_async():
    emitter = EventEmitter()

    def pipe_sync(payload):
        # modify in-place
        payload["sync_added"] = True
        return payload

    async def pipe_async(payload):
        # simulate async work
        await asyncio.sleep(0)
        payload["async_added"] = True
        return payload

    emitter.add_pipe("tool.observation", pipe_sync)
    emitter.add_pipe("tool.observation", pipe_async)

    result = emitter.emit_through_sync("tool.observation", {"original": True})

    assert result is not None
    assert result.get("original") is True
    assert result.get("sync_added") is True
    assert result.get("async_added") is True


def test_hooks_on_once_off():
    emitter = EventEmitter()
    calls = []

    def listener(payload):
        calls.append(("sync", payload))

    def once_listener(payload):
        calls.append(("once", payload))

    emitter.on("agent.thought", listener)
    emitter.once("agent.thought", once_listener)

    # First emit: both listeners should run
    emitter.emit_sync("agent.thought", {"val": 1})

    # Second emit: only the regular listener should run
    emitter.emit_sync("agent.thought", {"val": 2})

    # Validate calls
    assert ("sync", {"val": 1}) in calls
    assert ("once", {"val": 1}) in calls
    assert ("sync", {"val": 2}) in calls

    # once listener should have been called only once
    once_count = sum(1 for c in calls if c[0] == "once")
    assert once_count == 1
