"""
Test that command_line input properly handles user.input.request events.

When an agent uses the ask_user tool, it emits a user.input.request event
and waits for a user.input.response event. The command_line input component
must listen for these requests and respond appropriately.
"""

import asyncio
import pytest
from unittest.mock import patch
from woodwork.components.inputs.command_line import CommandLineInput
from woodwork.runtime.unified_event_bus import UnifiedEventBus
from woodwork.types.events import UserInputRequestPayload, UserInputResponsePayload


@pytest.fixture
def event_bus():
    """Create a fresh event bus for each test."""
    bus = UnifiedEventBus()
    return bus


@pytest.fixture
def command_line_input(event_bus):
    """Create command_line input with event bus."""
    cmd = CommandLineInput(name="test_cmd", component="input")
    # Manually set the event bus for testing
    cmd._event_bus = event_bus
    return cmd


@pytest.mark.skip(reason="TDD: user.input.request event handling not yet implemented in command_line")
@pytest.mark.asyncio
async def test_command_line_handles_user_input_request(event_bus, command_line_input):
    """Test that command_line listens for user.input.request and responds."""

    # Track if response was emitted
    response_received = asyncio.Future()
    captured_response = {}

    async def capture_response(payload):
        """Hook to capture the response event."""
        captured_response["payload"] = payload
        if not response_received.done():
            response_received.set_result(True)

    # Register hook to capture response
    event_bus.register_hook("user.input.response", capture_response)

    # Mock input() to return a test response
    with patch("builtins.input", return_value="Test answer from user"):
        # Create and emit a user input request
        request = UserInputRequestPayload(
            question="What is your name?",
            request_id="test-123",
            timeout_seconds=60,
            component_id="test_agent",
            component_type="agent",
        )

        await event_bus.emit("user.input.request", request)

        # Wait for response (with timeout)
        await asyncio.wait_for(response_received, timeout=2.0)

        # Verify response was emitted
        assert "payload" in captured_response
        response_payload = captured_response["payload"]

        # Check response content
        assert isinstance(response_payload, UserInputResponsePayload)
        assert response_payload.request_id == "test-123"
        assert response_payload.response == "Test answer from user"


@pytest.mark.skip(reason="TDD: user.input.request event handling not yet implemented in command_line")
@pytest.mark.asyncio
async def test_command_line_displays_question(event_bus, command_line_input):
    """Test that command_line displays the question to the user."""

    captured_prompts = []

    def mock_input(prompt=""):
        """Mock input that captures the prompt."""
        captured_prompts.append(prompt)
        return "answer"

    with patch("builtins.input", side_effect=mock_input):
        request = UserInputRequestPayload(
            question="What is 2+2?",
            request_id="test-456",
            timeout_seconds=60,
            component_id="test_agent",
            component_type="agent",
        )

        await event_bus.emit("user.input.request", request)
        await asyncio.sleep(0.1)  # Give time for async processing

        # Verify the question was shown to user
        assert len(captured_prompts) > 0
        assert "What is 2+2?" in captured_prompts[0]


@pytest.mark.skip(reason="TDD: user.input.request event handling not yet implemented in command_line")
@pytest.mark.asyncio
async def test_multiple_consecutive_asks(event_bus, command_line_input):
    """Test that command_line can handle multiple ask_user requests in sequence."""

    responses = []

    async def capture_response(payload):
        if isinstance(payload, UserInputResponsePayload):
            responses.append(payload)

    event_bus.register_hook("user.input.response", capture_response)

    # Mock input to return different answers
    mock_answers = iter(["First answer", "Second answer", "Third answer"])

    with patch("builtins.input", lambda p: next(mock_answers)):
        # Send three requests
        for i in range(3):
            request = UserInputRequestPayload(
                question=f"Question {i}?",
                request_id=f"req-{i}",
                timeout_seconds=60,
                component_id="test_agent",
                component_type="agent",
            )
            await event_bus.emit("user.input.request", request)
            await asyncio.sleep(0.1)  # Give time for processing

        # Verify all three responses were received
        assert len(responses) == 3
        assert responses[0].response == "First answer"
        assert responses[1].response == "Second answer"
        assert responses[2].response == "Third answer"
