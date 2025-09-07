"""
Simple event pipes that transform data and print when called.
"""
from datetime import datetime

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