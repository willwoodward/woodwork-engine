"""
Simple event hooks that print when called.
"""

def print_input_received(payload):
    """Hook that prints when agent receives input."""
    import logging
    logging.info(f"[HOOK] print_input_received called with payload: {payload}")
    print(f"🔔 INPUT RECEIVED: {payload.get('input', 'No input')}")
    print("Hook was called!", flush=True)

def print_agent_thought(payload):
    """Hook that prints agent thoughts."""
    print(f"💭 AGENT THOUGHT: {payload.get('thought', 'No thought')}")

def print_agent_action(payload):
    """Hook that prints agent actions."""
    action = payload.get('action', {})
    tool = action.get('tool', 'unknown')
    print(f"🔧 AGENT ACTION: Using tool '{tool}'")

def print_tool_call(payload):
    """Hook that prints tool calls."""
    tool = payload.get('tool', 'unknown')
    print(f"🚀 TOOL CALL: Executing {tool}")

def print_tool_observation(payload):
    """Hook that prints tool results."""
    tool = payload.get('tool', 'unknown')
    observation = str(payload.get('observation', ''))[:100]
    print(f"📋 TOOL RESULT from {tool}: {observation}...")

def print_step_complete(payload):
    """Hook that prints when steps complete."""
    step = payload.get('step', 'unknown')
    print(f"✅ STEP {step} COMPLETE")

def print_error(payload):
    """Hook that prints errors."""
    error = payload.get('error', 'Unknown error')
    print(f"❌ AGENT ERROR: {error}")