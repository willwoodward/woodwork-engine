# Event Hooks and Pipes Example

This example demonstrates the modular event system integration with woodwork components. You can now attach Python scripts directly to components via configuration, making event handling much more flexible and modular.

## Architecture

The event system has been integrated into the component base class, so any component can now have hooks and pipes attached via configuration. The system uses:

- **Hook Config**: `{event, script_path, function_name}` - Observers that don't modify data
- **Pipe Config**: `{event, script_path, function_name}` - Transformers that can modify data

## Files

- **`hooks.py`** - Simple functions that print when events occur
- **`pipes.py`** - Functions that transform data and print processing steps
- **`main_with_hooks.ww`** - Full example with comprehensive event monitoring
- **`main_simple_hooks.ww`** - Minimal example with just key events

## Usage

### 1. Basic Hook Configuration

```ww
coding_ag = agent llm {
    api_key: $OPENAI_API_KEY
    tools: [github_api, dev_env]
    
    hooks: [
        {
            event: "input.received"
            script_path: "hooks.py"
            function_name: "print_input_received"
        }
    ]
}
```

### 2. Pipe Configuration (Data Transformation)

```ww
coding_ag = agent llm {
    api_key: $OPENAI_API_KEY
    tools: [github_api, dev_env]
    
    pipes: [
        {
            event: "input.received"
            script_path: "pipes.py"
            function_name: "add_timestamp_to_input"
        }
    ]
}
```

## Available Events

### Agent Events
- `input.received` - When agent receives user input
- `agent.thought` - When agent has a reasoning thought  
- `agent.action` - When agent decides to take an action
- `agent.step_complete` - When a reasoning step completes
- `agent.error` - When an error occurs

### Tool Events  
- `tool.call` - Before a tool is executed
- `tool.observation` - After a tool returns results

## Writing Hook Functions

Hook functions receive a payload and should not return anything:

```python
def print_input_received(payload):
    """Hook that prints when agent receives input."""
    print(f"🔔 INPUT RECEIVED: {payload.get('input', 'No input')}")
```

## Writing Pipe Functions

Pipe functions receive a payload and should return the (possibly modified) payload:

```python
def add_timestamp_to_input(payload):
    """Pipe that adds timestamp to input."""
    print(f"🔄 PROCESSING INPUT: Adding timestamp")
    if isinstance(payload, dict):
        payload = payload.copy()
        payload['_timestamp'] = datetime.now().isoformat()
    return payload
```

## Running the Example

1. **Basic monitoring**: Use `main_simple_hooks.ww` to see key events
2. **Full monitoring**: Use `main_with_hooks.ww` to see all events and transformations
3. **Custom scripts**: Create your own `.py` files with hook/pipe functions

The system automatically loads the Python functions from the specified scripts and attaches them to the appropriate events. All errors are handled gracefully with logging.

## Benefits

- **Modular**: Each script contains focused functionality
- **Configurable**: Enable/disable hooks via config without code changes
- **Flexible**: Any component can have hooks/pipes attached
- **Safe**: Errors in hooks/pipes don't break the agent
- **Observable**: Full visibility into agent behavior
- **Extensible**: Easy to add new events and handlers