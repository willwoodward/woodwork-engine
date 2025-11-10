"""
Test ConversationSession for persistent context across inputs.
"""

import time
from woodwork.core.session import ConversationSession


def test_create_session():
    """Test basic session creation"""
    session = ConversationSession(id="test-123")

    assert session.id == "test-123"
    assert len(session.conversation_history) == 0
    assert len(session.workflow_variables) == 0
    assert session.current_prompt == ""


def test_add_turns():
    """Test adding conversation turns"""
    session = ConversationSession(id="test")

    session.add_turn("user", "Hello")
    session.add_turn("assistant", "Hi there")

    assert len(session.conversation_history) == 2
    assert session.conversation_history[0]["role"] == "user"
    assert session.conversation_history[0]["content"] == "Hello"
    assert session.conversation_history[1]["role"] == "assistant"
    assert session.conversation_history[1]["content"] == "Hi there"


def test_last_activity_updates():
    """Test that last_activity timestamp updates on turns"""
    session = ConversationSession(id="test")

    initial_time = session.last_activity
    time.sleep(0.01)

    session.add_turn("user", "Hello")

    assert session.last_activity > initial_time
