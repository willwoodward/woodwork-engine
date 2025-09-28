# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Installation & Setup
- `pip install woodwork-engine` - Install the main package
- `pip install -e .[all]` - Install in development mode with all optional dependencies
- `pip install pre-commit` - Install pre-commit hooks for linting/formatting
- `pre-commit install` - Enable pre-commit hooks
- `woodwork init` - Install dependencies for .ww config files (when working standalone)

### Common Operations
- `woodwork` - Run the main application (requires main.ww file)
- `woodwork --help` - Show available command line arguments
- `python dev-main.py` - Development entrypoint with custom logging
- `uv run ty check` - Type checking (used in pre-commit)

### Testing & Code Quality
- `pytest` - Run tests (test files located in `tests/` directory)
- `pytest tests/test_specific.py` - Run specific test file
- `pytest -k "test_name"` - Run specific test by name pattern
- `ruff check --fix` - Run linter with auto-fix
- `ruff format` - Format code
- Pre-commit hooks run `ruff-check`, `ruff-format`, and `ty check` automatically

## Architecture Overview

### Core Components
- **Parser** (`woodwork/parser/config_parser.py`) - Parses .ww configuration files into component declarations
- **Task Master** (`woodwork/core/task_master.py`) - Orchestrates task execution, manages workflows, and handles component communication
- **Component System** (`woodwork/components/`) - Modular architecture with components for LLMs, knowledge bases, inputs, outputs, APIs, and agents
- **Event System** (`woodwork/events/`) - JSON-first typed event system with hooks and pipes for component communication

### Configuration Language (.ww files)
- Custom declarative language for defining AI agent components
- Components are declared as `variable = component type { config }` 
- Supports dependency injection between components
- Environment variables referenced with `$VARIABLE_NAME`
- Hooks and pipes can be configured per component for event handling
- Examples available in `examples/` directory

### Event System Architecture
The event system provides type-safe, JSON-serializable payloads for component communication:

#### Event Types & Payloads
- All events use typed payloads located in `woodwork/types/events.py`
- Standard events: `input.received`, `agent.thought`, `agent.action`, `tool.call`, `tool.observation`, `agent.step_complete`, `agent.error`
- Payloads support JSON serialization via `to_json()` and `from_json()` methods
- Built-in validation via `validate()` method

#### Event Processing
- **Hooks**: Read-only listeners that run concurrently (debugging, logging)
- **Pipes**: Transform functions that run sequentially and can modify payloads
- **Events**: Fire-and-forget listeners (no return expected)

#### Component Attribution
- Events are automatically attributed to components via `EventSource` tracking
- Use `EventSource.track_component(component_id, component_type)` for component context
- Payloads include `component_id` and `component_type` fields

### Component Types
- **Agents** - LLM-powered agents with planning capabilities
- **LLMs** - OpenAI, Ollama, HuggingFace integrations
- **Knowledge Bases** - Chroma vector DB, Neo4j graph DB, text files
- **Inputs** - Command line, voice (keyword/push-to-talk)
- **APIs** - Web APIs, function tooling
- **Core** - Command line tools, code execution
- **Memory** - Short-term memory systems
- **Outputs** - Voice synthesis
- **Environments** - Coding environments with Docker integration

### Key Design Patterns
- Dependency resolution system automatically handles component relationships
- Router pattern for managing component deployments
- Component lifecycle management (initialization, starting, closing)
- Tool-based architecture where agents can invoke various tools
- Event-driven communication between components
- JSON-first serialization for HTTP/API compatibility
- Workflow caching in Neo4j for action plan reuse

### Type System
Types are centralized in `woodwork/types/`:
- `data_types.py` - Core data types (Data, Text, Audio, Image, Stream, Update)
- `events.py` - Event payload types with JSON serialization
- `event_source.py` - Component attribution system
- `prompts.py` - Prompt configuration types
- `workflows.py` - Action and workflow types

Import patterns:
- `from woodwork.types import InputReceivedPayload, EventSource`
- `from woodwork.events import emit, BasePayload`
- `from woodwork.payloads import ToolCallPayload, AgentThoughtPayload` (convenience imports for all payload types)

### File Structure
- `woodwork/components/` - All component implementations
- `woodwork/interfaces/` - Component interfaces and base classes
- `woodwork/deployments/` - Deployment and routing systems
- `woodwork/events/` - Event system with hooks, pipes, and typed payloads
- `woodwork/types/` - Type definitions for events, data, and workflows
- `woodwork/payloads.py` - Convenience imports for all event payload types
- `woodwork/core/` - Task master and core orchestration
- `woodwork/parser/` - .ww file parsing and configuration
- `examples/` - Sample .ww configurations demonstrating features
- `tests/` - Unit tests for parsers and core functionality

### Environment Configuration
- Copy `.env.example` to `.env` for environment variables
- API keys and secrets stored in environment variables
- Logging configured via `config/log_config.json`
- Development logging setup available via `dev-main.py`

## Event System Usage

### Writing Hooks and Pipes
Hooks and pipes can be written as Python functions and referenced in .ww configuration:

```python
# hooks.py
from woodwork.types import AgentThoughtPayload

def print_agent_thought(payload):
    if isinstance(payload, dict) and 'thought' in payload:
        print(f"Agent thought: {payload['thought']}")

# pipes.py  
from woodwork.types import InputReceivedPayload

def add_context_to_input(payload: InputReceivedPayload) -> InputReceivedPayload:
    # Modify and return the payload
    enhanced_input = f"Context: {payload.input}"
    return InputReceivedPayload(
        input=enhanced_input,
        inputs=payload.inputs,
        session_id=payload.session_id,
        component_id=payload.component_id,
        component_type=payload.component_type
    )
```

### JSON Event Handling
For HTTP/API integration, events support JSON serialization:

```python
from woodwork.types import PayloadRegistry

# Create payload from JSON (HTTP requests)
payload = PayloadRegistry.create_payload("tool.call", json_string)

# Validate event data
errors = PayloadRegistry.validate_event_data("agent.thought", {"thought": ""})

# Get schema information
schema = PayloadRegistry.get_event_schema("input.received")
```

## Development Workflow

### Component Development
1. Implement component interface in `woodwork/components/`
2. Add component type to parser in `woodwork/parser/`
3. Create example .ww configuration in `examples/`
4. Add tests in `tests/`

### Event System Extension
1. Add new payload types to `woodwork/types/events.py`
2. Register in `PayloadRegistry._registry`
3. Update `__all__` exports in `woodwork/types/__init__.py`
4. Create example hooks/pipes demonstrating usage

### Testing Strategy
- Unit tests for individual components
- Integration tests for .ww file parsing
- Event system tests for payload validation
- Example configurations serve as integration tests