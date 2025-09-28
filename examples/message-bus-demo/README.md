# Message Bus Demo

This example demonstrates Woodwork's new distributed message bus system that replaces the centralized Task Master with declarative component-to-component communication.

## Key Features

### 🔄 **Declarative Routing**
Components declare where their outputs go using the `to:` property:
```ww
agent = claude {
    model = "claude-3-sonnet"
    to = ["output", "websocket", "logger"]  # Multiple destinations
}
```

### 🚀 **Zero Configuration**
The message bus works out-of-the-box with intelligent defaults:
- **Development**: In-memory message bus for fast iteration
- **Production**: Automatically detects Redis/NATS from environment
- **No setup required** - components communicate immediately

### 🔌 **Seamless Integration** 
- **Existing API preserved**: `emit()` continues to work for local events
- **Enhanced with routing**: `emit()` automatically routes to configured targets
- **Direct messaging**: `send_to_component()` for explicit communication
- **Hooks & pipes unchanged**: All existing event processing works identically

### 📊 **Enterprise Features**
- **Reliability**: Message ordering, retry logic, dead letter queues
- **Monitoring**: Comprehensive metrics and health checking
- **Session isolation**: Multi-tenant support built-in
- **Backpressure handling**: Automatic flow control

## Running the Demo

### Basic Usage (No Configuration Required)

```bash
# Just run it - uses in-memory message bus automatically
woodwork

# Set debug logging to see message routing
WOODWORK_LOG_LEVEL=DEBUG woodwork
```

### With Redis (Production-like)

```bash
# Start Redis
docker run -d -p 6379:6379 redis:alpine

# Set Redis URL and run
export REDIS_URL=redis://localhost:6379
woodwork
```

### With Custom Message Bus Configuration

Edit the `main.ww` file to uncomment the message bus configuration:

```ww
deployment = local {
    message_bus = redis {
        redis_url = $REDIS_URL
        stream_prefix = "woodwork_demo" 
        consumer_group = "demo_components"
        max_retries = 5
    }
}
```

## How It Works

### 1. **Component Independence**
Components no longer depend on Task Master for orchestration:

```python
# Component just emits events - doesn't know about routing
class LLMComponent(component):
    async def process(self, input_text):
        response = await self.generate_response(input_text)
        
        # This automatically routes to configured 'to:' targets
        await self.emit("response_generated", response)
        return response
```

### 2. **Distributed Routing**
The message bus reads `.ww` configuration and builds routing tables:

```python
routing_table = {
    "agent": ["output", "websocket", "logger"],  # From 'to:' property
    "input": ["agent"],                          # Inferred workflow
    "memory": ["agent"]                          # Feedback loop
}
```

### 3. **Event Processing**
Messages flow through the existing event system:

```
Input Component
    ↓ (message bus)
Agent Component
    ↓ (pipes: add_context)
    ↓ (hooks: log_response) 
    ↓ (message bus routing)
Output + WebSocket + Logger Components
    ↓ (each applies own pipes/hooks)
Display/Send/Store Results
```

## Debug Logging

Enable debug logging to see the message bus in action:

```bash
export WOODWORK_LOG_LEVEL=DEBUG
woodwork
```

You'll see logs like:
```
[MessageBusFactory] Creating global message bus instance
[DeclarativeRouter] Configuring routing from 7 components  
[DeclarativeRouter] Component 'agent' routes to: ['output', 'websocket', 'logger']
[InMemoryMessageBus] Publishing 'response_generated' to 3 targets
[MessageBusIntegration] Auto-routed 'response_generated' from agent to output
[Component output] Received 'response_generated' from agent
```

## Compared to Task Master

### Before (Task Master - Centralized)
```python
# Centralized orchestration
task_master.add_tools([input_comp, agent_comp, output_comp])
result = task_master.execute(action)  # Single point of control
```

### After (Message Bus - Distributed)  
```python
# Distributed communication
input_comp.emit("user_input", data)           # Routes to agent automatically
agent_comp.emit("response_generated", result) # Routes to output automatically  
output_comp.display(result)                   # Receives via message bus
```

## Configuration Examples

### Simple Routing
```ww
agent = claude {
    to = "output"  # Single target
}
```

### Multi-target Routing  
```ww
agent = claude {
    to = ["output", "websocket", "analytics"]  # Multiple targets
}
```

### No Configuration (Inferred)
```ww
input = cli {}      # Will route to agent (inferred)
agent = claude {}   # Will route to output (inferred)  
output = cli {}     # End of chain
```

### Complex Patterns
```ww
memory = memory {
    to = ["agent"]  # Feedback to agent
}

analytics = analytics {
    # Receives from agent and logger (many-to-one)
}

agent = claude {
    to = ["output", "memory", "analytics"]  # One-to-many
}
```

This demonstrates how the message bus enables complex distributed workflows while maintaining the simple, declarative configuration that Woodwork users expect.