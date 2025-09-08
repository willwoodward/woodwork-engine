"""
Event pipes for adding CLAUDE.md context to agent inputs.
"""
import os
from datetime import datetime

def add_claude_md_to_input(payload):
    """Pipe that prepends CLAUDE.md content to the input message."""
    import logging
    import sys
    
    msg = "🔄 ADDING CLAUDE.MD CONTEXT"
    print(msg, flush=True)
    logging.info(f"[PIPE] {msg}")
    sys.stdout.flush()
    
    if not isinstance(payload, dict):
        return payload
    
    payload = payload.copy()
    current_input = payload.get('input', '')
    
    # Look for CLAUDE.md file in current directory and parent directories
    claude_md_path = find_claude_md()
    
    if claude_md_path and os.path.exists(claude_md_path):
        try:
            with open(claude_md_path, 'r', encoding='utf-8') as f:
                claude_content = f.read()
            
            # Prepend CLAUDE.md content to the input
            enhanced_input = f"""
<project_context>
{claude_content}
</project_context>

{current_input}"""
            
            payload['input'] = enhanced_input
            payload['_claude_md_added'] = True
            payload['_claude_md_path'] = claude_md_path
            
            success_msg = f"✅ Added CLAUDE.md content from: {claude_md_path}"
            print(success_msg, flush=True)
            logging.info(f"[PIPE] {success_msg}")
            sys.stdout.flush()
        except Exception as e:
            error_msg = f"⚠️  Error reading CLAUDE.md: {e}"
            print(error_msg, flush=True)
            logging.warning(f"[PIPE] {error_msg}")
            sys.stdout.flush()
    else:
        not_found_msg = "⚠️  CLAUDE.md not found"
        print(not_found_msg, flush=True)
        logging.info(f"[PIPE] {not_found_msg}")
        sys.stdout.flush()
    
    return payload

def find_claude_md(start_dir=None):
    """Find CLAUDE.md file by searching up the directory tree."""
    if start_dir is None:
        start_dir = os.getcwd()
    
    current_dir = os.path.abspath(start_dir)
    
    while True:
        claude_md_path = os.path.join(current_dir, 'CLAUDE.md')
        if os.path.exists(claude_md_path):
            return claude_md_path
        
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:  # Reached root directory
            break
        current_dir = parent_dir
    
    return None

def add_timestamp_to_input(payload):
    """Pipe that adds timestamp to input."""
    print(f"🔄 PROCESSING INPUT: Adding timestamp")
    if isinstance(payload, dict):
        payload = payload.copy()
        payload['_timestamp'] = datetime.now().isoformat()
    return payload

def validate_action(payload):
    """Pipe that validates actions."""
    print(f"🔍 VALIDATING ACTION")
    action = payload.get('action', {}) if isinstance(payload, dict) else {}
    
    if not action.get('tool'):
        print(f"⚠️  WARNING: Action missing tool name")
    if not action.get('action'):
        print(f"⚠️  WARNING: Action missing action description")
        
    return payload

def log_tool_call(payload):
    """Pipe that logs tool calls."""
    tool = payload.get('tool', 'unknown') if isinstance(payload, dict) else 'unknown'
    print(f"📞 LOGGING TOOL CALL: {tool}")
    
    # Add metadata
    if isinstance(payload, dict):
        payload = payload.copy()
        payload['_logged_at'] = datetime.now().isoformat()
    
    return payload

def process_observation(payload):
    """Pipe that processes tool observations."""
    if isinstance(payload, dict):
        observation = payload.get('observation', '')
        tool = payload.get('tool', 'unknown')
        
        print(f"🔄 PROCESSING OBSERVATION from {tool}")
        
        # Truncate very long observations
        if len(str(observation)) > 500:
            payload = payload.copy()
            payload['observation'] = str(observation)[:500] + "... [truncated]"
            payload['_truncated'] = True
            print(f"✂️  Truncated long observation")
    
    return payload