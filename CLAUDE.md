# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Installation & Setup
- `pip install woodwork-engine` - Install the main package
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
- `ruff check --fix` - Run linter with auto-fix
- `ruff format` - Format code
- Pre-commit hooks run `ruff-check`, `ruff-format`, and `ty check` automatically

## Architecture Overview

### Core Components
- **Parser** (`woodwork/parser/config_parser.py`) - Parses .ww configuration files into component declarations
- **Task Master** (`woodwork/core/task_master.py`) - Orchestrates task execution, manages workflows, and handles component communication
- **Component System** - Modular architecture with components for LLMs, knowledge bases, inputs, outputs, APIs, and agents

### Configuration Language (.ww files)
- Custom declarative language for defining AI agent components
- Components are declared as `variable = component type { config }` 
- Supports dependency injection between components
- Environment variables referenced with `$VARIABLE_NAME`
- Examples available in `examples/` directory

### Component Types
- **Agents** - LLM-powered agents with planning capabilities
- **LLMs** - OpenAI, Ollama, HuggingFace integrations
- **Knowledge Bases** - Chroma vector DB, Neo4j graph DB, text files
- **Inputs** - Command line, voice (keyword/push-to-talk)
- **APIs** - Web APIs, function tooling
- **Core** - Command line tools, code execution
- **Memory** - Short-term memory systems
- **Outputs** - Voice synthesis

### Key Design Patterns
- Dependency resolution system automatically handles component relationships
- Router pattern for managing component deployments
- Component lifecycle management (initialization, starting, closing)
- Tool-based architecture where agents can invoke various tools
- Workflow caching in Neo4j for action plan reuse

### File Structure
- `woodwork/components/` - All component implementations
- `woodwork/interfaces/` - Component interfaces and base classes
- `woodwork/deployments/` - Deployment and routing systems
- `examples/` - Sample .ww configurations demonstrating features
- `tests/` - Unit tests for parsers and core functionality

### Environment Configuration
- Copy `.env.example` to `.env` for environment variables
- API keys and secrets stored in environment variables
- Logging configured via `config/log_config.json`