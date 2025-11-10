"""
Test AsyncRuntime session management
"""

import pytest
from woodwork.core.async_runtime import AsyncRuntime


@pytest.mark.asyncio
async def test_runtime_get_or_create_session():
    """Test getting or creating sessions"""
    runtime = AsyncRuntime()

    session1 = runtime._get_or_create_session("sess-1")
    session2 = runtime._get_or_create_session("sess-1")  # Same ID

    assert session1.id == session2.id
    assert session1 is session2  # Same object


@pytest.mark.asyncio
async def test_multiple_sessions():
    """Test multiple sessions are isolated"""
    runtime = AsyncRuntime()

    session1 = runtime._get_or_create_session("sess-1")
    session2 = runtime._get_or_create_session("sess-2")

    session1.add_turn("user", "Message 1")
    session2.add_turn("user", "Message 2")

    assert len(session1.conversation_history) == 1
    assert len(session2.conversation_history) == 1
    assert session1.conversation_history[0]["content"] != session2.conversation_history[0]["content"]
