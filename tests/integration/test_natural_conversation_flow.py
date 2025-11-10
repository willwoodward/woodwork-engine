"""
Integration test: Natural conversation flow replaces ask_user tool.

Tests that agents can ask questions by returning them as Final Answer,
and that sessions preserve context so the user's response continues the conversation.
"""
import pytest
from woodwork.core.session import ConversationSession

pytestmark = [pytest.mark.slow, pytest.mark.integration]


@pytest.mark.integration
def test_natural_conversation_flow_concept():
    """
    Test the concept: Agent asks question → User responds → Agent has context

    This tests the session mechanics, not the actual LLM.
    """
    session = ConversationSession(id="test")

    # Turn 1: Agent needs info, returns question as Final Answer
    agent_question = "What port should the server use?"
    session.add_turn("assistant", agent_question)
    session.current_prompt = f"User: Configure the server\n\nAssistant: {agent_question}"

    # Verify session saved the question
    assert len(session.conversation_history) == 1
    assert "port" in session.conversation_history[0]["content"].lower()

    # Turn 2: User responds
    user_response = "Port 8080"
    session.add_turn("user", user_response)
    session.current_prompt += f"\n\nUser: {user_response}"

    # Agent would now see full context in session.current_prompt
    assert "Configure the server" in session.current_prompt
    assert "What port" in session.current_prompt
    assert "8080" in session.current_prompt

    # Turn 3: Agent can now complete task with context
    final_response = "Server configured on port 8080"
    session.add_turn("assistant", final_response)

    # Verify full conversation preserved
    assert len(session.conversation_history) == 3
    assert session.conversation_history[0]["role"] == "assistant"  # Question
    assert session.conversation_history[1]["role"] == "user"       # Answer
    assert session.conversation_history[2]["role"] == "assistant"  # Completion


@pytest.mark.integration
def test_multiple_clarifications():
    """Test multiple back-and-forth clarifications"""
    session = ConversationSession(id="test")

    # Initial request
    session.add_turn("user", "Deploy the application")
    session.current_prompt = "User: Deploy the application"

    # Clarification 1: Which environment?
    session.add_turn("assistant", "Which environment: staging or production?")
    session.current_prompt += "\n\nAssistant: Which environment: staging or production?"

    session.add_turn("user", "Production")
    session.current_prompt += "\n\nUser: Production"

    # Clarification 2: Which version?
    session.add_turn("assistant", "Which version should I deploy?")
    session.current_prompt += "\n\nAssistant: Which version should I deploy?"

    session.add_turn("user", "Version 2.1.0")
    session.current_prompt += "\n\nUser: Version 2.1.0"

    # Final completion
    session.add_turn("assistant", "Deploying version 2.1.0 to production")

    # Verify all context preserved
    assert len(session.conversation_history) == 6
    assert "Production" in session.current_prompt
    assert "2.1.0" in session.current_prompt
    assert "Deploy the application" in session.current_prompt


@pytest.mark.integration
def test_workflow_variables_preserved_across_questions():
    """Test that workflow variables persist through clarification questions"""
    session = ConversationSession(id="test")

    # Agent starts task, discovers it needs info
    session.workflow_variables["task"] = "database_migration"
    session.workflow_variables["status"] = "awaiting_confirmation"

    # Agent asks question
    session.add_turn("assistant", "This will migrate the database. Continue? (yes/no)")

    # User responds
    session.add_turn("user", "yes")

    # Agent resumes - workflow variables should still be there
    assert session.workflow_variables["task"] == "database_migration"
    assert session.workflow_variables["status"] == "awaiting_confirmation"

    # Agent updates variables and completes
    session.workflow_variables["status"] = "completed"
    session.add_turn("assistant", "Database migration completed")

    assert session.workflow_variables["status"] == "completed"
