import os
from typing import Optional

from woodwork.types import InputReceivedPayload


def add_claude_md_to_input(payload: InputReceivedPayload) -> InputReceivedPayload:
    """Pipe that adds CLAUDE.md context to input payloads."""

    # Type check - this pipe only handles InputReceivedPayload
    if not isinstance(payload, InputReceivedPayload):
        print(f"⚠️  Expected InputReceivedPayload, got {type(payload)}")
        return payload

    # Check if this is a continuing session - if so, skip adding CLAUDE.md
    # (it's already in the session context from the first turn)
    session = payload.inputs.get("_session") if payload.inputs else None
    if session and len(session.conversation_history) > 0:
        print("ℹ️  Skipping CLAUDE.md (already in session context)")
        return payload

    # Look for CLAUDE.md file
    claude_md_path = find_claude_md()

    if claude_md_path and os.path.exists(claude_md_path):
        try:
            with open(claude_md_path, "r", encoding="utf-8") as f:
                claude_content = f.read()

            enhanced_input = f"""
<project_context>
{claude_content}
</project_context>

{payload.input}"""

            # Create new payload with enhanced input
            enhanced_payload = InputReceivedPayload(
                input=enhanced_input,
                inputs=payload.inputs,
                session_id=payload.session_id,
                timestamp=payload.timestamp,
                component_id=payload.component_id,
                component_type=payload.component_type,
            )

            print(f"✅ Added CLAUDE.md content from: {claude_md_path}")
            return enhanced_payload

        except Exception as e:
            print(f"⚠️  Error reading CLAUDE.md: {e}")
    else:
        print("⚠️  CLAUDE.md not found")

    return payload


def find_claude_md(start_dir: Optional[str] = None) -> Optional[str]:
    """Find CLAUDE.md file by searching up the directory tree."""
    if start_dir is None:
        start_dir = os.getcwd()

    current_dir = os.path.abspath(start_dir)

    while True:
        claude_md_path = os.path.join(current_dir, "CLAUDE.md")
        if os.path.exists(claude_md_path):
            return claude_md_path

        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:  # Reached root directory
            break
        current_dir = parent_dir

    return None
