"""Event hooks for the life assistant example."""


def print_thought(payload):
    """Print agent thoughts for visibility."""
    if isinstance(payload, dict):
        thought = payload.get("thought", "")
    else:
        thought = getattr(payload, "thought", "")
    if thought:
        print(f"  [thinking] {thought}")


def print_tool_call(payload):
    """Print tool calls for visibility."""
    if isinstance(payload, dict):
        tool_name = payload.get("tool", payload.get("tool_name", "unknown"))
    else:
        tool_name = getattr(payload, "tool", getattr(payload, "tool_name", "unknown"))
    print(f"  [tool] Calling: {tool_name}")
