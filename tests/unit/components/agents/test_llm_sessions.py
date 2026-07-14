"""
Test agent session support for persistent context.
"""

from woodwork.runtime.session import ConversationSession


def test_session_workflow_variables():
    """Test session stores and retrieves workflow variables"""
    session = ConversationSession(id="test")

    # Simulate agent setting workflow variables
    session.workflow_variables["x"] = 10
    session.workflow_variables["name"] = "Alice"

    assert session.workflow_variables["x"] == 10
    assert session.workflow_variables["name"] == "Alice"


def test_session_current_prompt_accumulation():
    """Test session accumulates prompt context"""
    session = ConversationSession(id="test")

    # Simulate agent building up prompt
    session.current_prompt = "User: Hello"
    session.current_prompt += "\n\nAssistant: Hi there"
    session.current_prompt += "\n\nUser: My name is Alice"

    assert "Hello" in session.current_prompt
    assert "Alice" in session.current_prompt
    assert len(session.current_prompt) > 20


def test_session_history_with_agent_responses():
    """Test session tracks full conversation history"""
    session = ConversationSession(id="test")

    # Simulate conversation
    session.add_turn("user", "My name is Alice")
    session.add_turn("assistant", "Nice to meet you, Alice!")
    session.add_turn("user", "What's my name?")
    session.add_turn("assistant", "Your name is Alice")

    assert len(session.conversation_history) == 4
    assert session.conversation_history[0]["role"] == "user"
    assert session.conversation_history[1]["content"] == "Nice to meet you, Alice!"
    assert session.conversation_history[3]["content"] == "Your name is Alice"
