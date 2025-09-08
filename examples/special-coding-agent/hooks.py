"""
Simple event hooks that print when called.
"""

def print_input_received(payload):
    """Hook that prints when agent receives input."""
    msg = f"🔔 INPUT RECEIVED: {payload.get('input', 'No input') if isinstance(payload, dict) else payload}"
    print(msg, flush=True)

def print_agent_thought(payload):
    """Hook that prints agent thoughts."""
    msg = f"💭 AGENT THOUGHT: {payload.get('thought', 'No thought') if isinstance(payload, dict) else payload}"
    print(msg, flush=True)

def print_agent_action(payload):
    """Hook that prints agent actions."""
    if isinstance(payload, dict):
        action = payload.get('action', {})
        tool = action.get('tool', 'unknown') if isinstance(action, dict) else 'unknown'
    else:
        tool = 'unknown'
    msg = f"🔧 AGENT ACTION: Using tool '{tool}'"
    print(msg, flush=True)

def print_tool_call(payload):
    """Hook that prints tool calls."""
    tool = payload.get('tool', 'unknown') if isinstance(payload, dict) else 'unknown'
    msg = f"🚀 TOOL CALL: Executing {tool}"
    print(msg, flush=True)

def print_tool_observation(payload):
    """Hook that prints tool results."""
    if isinstance(payload, dict):
        tool = payload.get('tool', 'unknown')
        observation = str(payload.get('observation', ''))[:100]
    else:
        tool = 'unknown'
        observation = str(payload)[:100]
    msg = f"📋 TOOL RESULT from {tool}: {observation}..."
    print(msg, flush=True)

def print_step_complete(payload):
    """Hook that prints when steps complete."""
    step = payload.get('step', 'unknown') if isinstance(payload, dict) else 'unknown'
    msg = f"✅ STEP {step} COMPLETE"
    print(msg, flush=True)

def print_error(payload):
    """Hook that prints errors."""
    error = payload.get('error', 'Unknown error') if isinstance(payload, dict) else payload
    msg = f"❌ AGENT ERROR: {error}"
    print(msg, flush=True)