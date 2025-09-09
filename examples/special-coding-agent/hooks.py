"""
Simple event hooks that print when called.
"""

from woodwork.types import (
    InputReceivedPayload, 
    AgentThoughtPayload, 
    AgentActionPayload, 
    ToolCallPayload, 
    ToolObservationPayload, 
    AgentStepCompletePayload, 
    AgentErrorPayload
)

def print_input_received(payload: InputReceivedPayload):
    """Hook that prints when agent receives input."""
    msg = f"🔔 INPUT RECEIVED: {payload.input}"
    print(msg, flush=True)

def print_agent_thought(payload: AgentThoughtPayload):
    """Hook that prints agent thoughts."""
    msg = f"💭 AGENT THOUGHT: {payload.thought}"
    print(msg, flush=True)

def print_agent_action(payload: AgentActionPayload):
    """Hook that prints agent actions."""
    action = payload.action
    tool = action.get('tool', 'unknown') if isinstance(action, dict) else 'unknown'
    msg = f"🔧 AGENT ACTION: Using tool '{tool}'"
    print(msg, flush=True)

def print_tool_call(payload: ToolCallPayload):
    """Hook that prints tool calls."""
    msg = f"🚀 TOOL CALL: Executing {payload.tool}"
    print(msg, flush=True)

def print_tool_observation(payload: ToolObservationPayload):
    """Hook that prints tool results."""
    observation = str(payload.observation)[:100]
    msg = f"📋 TOOL RESULT from {payload.tool}: {observation}..."
    print(msg, flush=True)

def print_step_complete(payload: AgentStepCompletePayload):
    """Hook that prints when steps complete."""
    msg = f"✅ STEP {payload.step} COMPLETE"
    print(msg, flush=True)

def print_error(payload: AgentErrorPayload):
    """Hook that prints errors."""
    msg = f"❌ AGENT ERROR: {payload.error}"
    print(msg, flush=True)