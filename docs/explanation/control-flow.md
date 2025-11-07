---
title: Control Flow
description: Understanding events, hooks, and pipes in Woodwork
index: 1
---

# Control Flow: Events, Hooks & Pipes

Woodwork components communicate through **events**. As data flows through your agent, events fire at key moments. You can observe and transform this flow using **hooks** and **pipes**.

## Events: How Components Communicate

When things happen in your agent, Woodwork emits events:

- `input.received` - User provides input
- `agent.thought` - Agent is reasoning about the task
- `tool.call` - Agent invokes a tool
- `tool.observation` - Tool returns a result
- `llm.response_generated` - LLM generates a response

Events carry **payloads** - structured data about what happened. Components emit events, and other components (or your hooks/pipes) can react to them.

## Hooks: Read-Only Listeners

**Hooks are functions that run when events occur.** They cannot modify data - they only observe.

**Use hooks for:**
- Logging and debugging
- Monitoring and metrics
- Auditing and compliance
- Notifications and alerts

**Example: Logging LLM responses**

In your `main.ww`:
```ww
my_llm = llm openai {
    model: "gpt-4o-mini"
    api_key: $OPENAI_API_KEY

    hooks = [
        { event: "llm.response_generated", function: "log_response", script: "hooks/logging.py" }
    ]
}
```

In `hooks/logging.py`:
```python
import logging

log = logging.getLogger(__name__)

def log_response(payload):
    """Log all LLM responses for debugging"""
    if isinstance(payload, dict):
        response = payload.get('data', payload)
        log.info(f"LLM Response: {str(response)[:100]}...")
```

The hook runs every time `llm.response_generated` fires, but it doesn't change the response - it just logs it.

## Pipes: Transform Data Flow

**Pipes are functions that transform event payloads.** They receive data, modify it, and return the modified version.

**Use pipes for:**
- Adding context to user input
- Formatting data for specific components
- Enriching payloads with metadata
- Validating and normalizing data

**Example: Adding context to user input**

In your `main.ww`:
```ww
my_agent = llm openai {
    model: "gpt-4o-mini"
    api_key: $OPENAI_API_KEY

    pipes = [
        { event: "input.received", function: "add_context", script: "pipes/context.py" }
    ]
}
```

In `pipes/context.py`:
```python
def add_context(payload):
    """Add contextual information to user input"""
    if not isinstance(payload, dict):
        payload = {"data": payload}

    # Add system context
    enhanced_payload = {
        **payload,
        "context": {
            "timestamp": time.time(),
            "user_role": "developer",
            "priority": "normal"
        }
    }

    return enhanced_payload
```

The pipe intercepts `input.received` events, adds context, and returns the enriched payload. Downstream components receive the modified data.

## Hooks vs Pipes: When to Use Each

| Feature | Hooks | Pipes |
|---------|-------|-------|
| **Modify data?** | No (read-only) | Yes (transforms payload) |
| **Execution** | Run concurrently | Run sequentially |
| **Return value** | Ignored | Must return payload |
| **Use cases** | Logging, monitoring, alerts | Data enrichment, validation, formatting |

**Simple rule:** If you need to change the data, use a **pipe**. If you just need to observe, use a **hook**.

## Multiple Hooks and Pipes

You can attach multiple hooks and pipes to a component:

```ww
my_agent = agent llm {
    model: language_model

    hooks = [
        { event: "agent.thought", function: "log_thought", script: "hooks/logging.py" },
        { event: "tool.call", function: "monitor_tools", script: "hooks/monitoring.py" }
    ]

    pipes = [
        { event: "input.received", function: "add_context", script: "pipes/context.py" },
        { event: "input.received", function: "validate_input", script: "pipes/validation.py" }
    ]
}
```

- **Hooks** run concurrently (order doesn't matter)
- **Pipes** run sequentially in the order declared (output of one becomes input to the next)

## Routing: Declarative Message Passing

Components can explicitly route their outputs using the `to:` property:

```ww
input = input command_line {
    to: my_agent
}

my_agent = agent llm {
    model: language_model
    to: [output, logger, analytics]  # Multi-target routing
}
```

This declares where events should flow. Woodwork automatically routes messages between components based on these declarations.

## Complete Example

Here's a full configuration with hooks, pipes, and routing:

```ww
# Components
my_llm = llm openai {
    model: "gpt-4o-mini"
    api_key: $OPENAI_API_KEY

    hooks = [
        { event: "llm.response_generated", function: "log_response", script: "hooks/logging.py" }
    ]

    pipes = [
        { event: "input.received", function: "add_context", script: "pipes/context.py" }
    ]
}

input = input command_line {
    to: my_llm
}
```

**What happens when you type a message:**

1. `input.received` event fires
2. `add_context` pipe runs → adds metadata to input
3. Enhanced input routes to `my_llm`
4. LLM generates response → `llm.response_generated` fires
5. `log_response` hook runs → logs the response
6. Response displays to user

All of this orchestration is automatic. You just declared what should happen.

## Best Practices

**Keep hooks and pipes simple:**
- One responsibility per function
- Handle errors gracefully (log and return original payload)
- Avoid long-running operations in pipes (they block the event flow)

**Use typed payloads:**
```python
from woodwork.types import InputReceivedPayload

def add_context(payload: InputReceivedPayload) -> InputReceivedPayload:
    # Type hints help catch errors early
    pass
```

**Test your hooks and pipes:**
```python
def test_add_context():
    payload = {"data": "test input"}
    result = add_context(payload)
    assert "context" in result
```

## Next Steps

- See `woodwork/types/events.py` for all available event types
- Read the glossary for definitions of event-related terms
