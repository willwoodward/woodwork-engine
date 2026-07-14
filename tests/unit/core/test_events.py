"""Tests for woodwork.core.events.EventBus."""

import asyncio
import pytest

from woodwork.core.events import EventBus


@pytest.mark.asyncio
async def test_hook_called():
    bus = EventBus()
    called = []
    bus.register_hook("test.event", lambda p: called.append(p))
    await bus.emit("test.event", {"x": 1})
    assert called == [{"x": 1}]


@pytest.mark.asyncio
async def test_pipe_transforms():
    bus = EventBus()

    def double(payload):
        return {"x": payload["x"] * 2}

    bus.register_pipe("test.event", double)
    result = await bus.emit("test.event", {"x": 3})
    assert result == {"x": 6}


@pytest.mark.asyncio
async def test_pipe_chain():
    bus = EventBus()
    bus.register_pipe("e", lambda p: p + 1)
    bus.register_pipe("e", lambda p: p * 10)
    result = await bus.emit("e", 1)
    assert result == 20  # (1+1)*10


@pytest.mark.asyncio
async def test_fire_and_forget_event():
    bus = EventBus()
    called = []

    async def listener(p):
        await asyncio.sleep(0)
        called.append(p)

    bus.register_event("e", listener)
    await bus.emit("e", "hello")
    # Allow tasks to run
    await asyncio.sleep(0.05)
    assert called == ["hello"]


@pytest.mark.asyncio
async def test_parent_bubbling():
    parent = EventBus()
    child = EventBus(parent=parent)

    seen_parent = []
    parent.register_hook("e", lambda p: seen_parent.append(p))

    await child.emit("e", "data")
    assert seen_parent == ["data"]


@pytest.mark.asyncio
async def test_no_cross_event_leakage():
    bus = EventBus()
    called = []
    bus.register_hook("a.event", lambda p: called.append(p))
    await bus.emit("b.event", "payload")
    assert called == []


def test_stats():
    bus = EventBus()
    bus.register_hook("e", lambda p: None)
    bus.register_pipe("e", lambda p: p)
    bus.register_event("e", lambda p: None)
    s = bus.stats()
    assert s["hooks"] == 1
    assert s["pipes"] == 1
    assert s["events"] == 1
