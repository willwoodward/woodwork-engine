# woodwork-engine

[![PyPI - Version](https://img.shields.io/pypi/v/woodwork-engine.svg?logo=pypi&label=PyPI&logoColor=gold)](https://pypi.org/project/woodwork-engine/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/woodwork-engine.svg?logo=python&label=Python&logoColor=gold)](https://pypi.org/project/woodwork-engine/)
[![PyPI - Installs](https://img.shields.io/pypi/dm/woodwork-engine.svg?color=blue&label=Installs&logo=pypi&logoColor=gold)](https://pypi.org/project/woodwork-engine/)
[![License](https://img.shields.io/github/license/willwoodward/woodwork-engine?label=License&logo=open-source-initiative)](https://github.com/willwoodward/woodwork-engine/blob/main/LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/willwoodward/woodwork-engine?label=Stars&logo=github)](https://github.com/willwoodward/woodwork-engine/stargazers)

**Build AI agents with configuration, not code.**

Woodwork Engine lets you define AI agents using a simple declarative language (`.ww` files). Declare what you want—components, connections, and behavior—and Woodwork handles the rest.

## Table of Contents

- [Why Woodwork?](#why-woodwork)
- [Features](#features)
- [Quick Start](#quick-start)
- [Documentation](#documentation)
- [Examples](#examples)
- [Contributing](#contributing)
- [License](#license)

## Why Woodwork?

Building AI agents usually means:
- Writing boilerplate code over and over
- Managing complex integrations between LLMs, tools, and data sources
- Maintaining brittle orchestration logic

Woodwork takes a different approach: **Infrastructure as Code for AI agents.**

Instead of writing Python to wire everything together, you declare your agent in a `.ww` file:

```ww
my_agent = agent llm {
    model: language_model
    tools: [web_search, calculator]
}

input = input command_line {
    to: my_agent
}
```

That's it. Woodwork handles orchestration, tool calling, memory, and communication.

![Screenshot 2025-01-01 160031](https://github.com/user-attachments/assets/1a1c759e-aa5e-4499-902f-6d8abd23b3b8)

## Features

**Declarative Configuration**
- Define agents in simple `.ww` files instead of writing Python
- Components are modular and reusable
- Environment variables for secrets (`$OPENAI_API_KEY`)

**Powerful Control Flow**
- **Hooks**: Listen to events for logging and monitoring
- **Pipes**: Transform data as it flows between components
- **Routing**: Declarative message passing between components

**Rich Integrations**
- LLMs: OpenAI, Ollama, HuggingFace
- Knowledge: Vector databases (Chroma), graph databases (Neo4j), text files
- Tools: Function calling, web APIs, command-line tools
- I/O: CLI, voice input/output, streaming

## Quick Start

```bash
# Install
pip install woodwork-engine

# Create a simple agent configuration
cat > main.ww << 'EOF'
my_llm = llm openai {
  model: "gpt-4o-mini"
  api_key: $OPENAI_API_KEY
}

input = input command_line {
  to: my_llm
}
EOF

# Set up your API key
echo "OPENAI_API_KEY=your-key-here" > .env

# Install dependencies and run
woodwork --init
woodwork
```

That's it! You now have a running AI agent.

## Documentation

- **[Quickstart Guide](docs/quickstart.md)** - Get up and running in 5 minutes
- **[Beginner Overview](docs/beginner-overview.md)** - Understand the core concepts
- **[Philosophy](docs/explanation/philosophy.md)** - Why Infrastructure as Code for agents?
- **[Control Flow](docs/explanation/control-flow.md)** - Master hooks, pipes, and events
- **[Glossary](docs/glossary.md)** - Common terms and definitions

## Examples

Check out the `examples/` directory for ready-to-run configurations:

- **`01-short-term-memory-agent/`** - Agent with conversational memory
- **`02-function-tooling-agent/`** - Agent that can call custom functions
- **`04-plan-caching-agent/`** - Agent with workflow caching for repeated tasks
- **`message-bus-demo/`** - Advanced routing with hooks and pipes

Each example includes a `main.ww` file and any required Python scripts. Just add your API keys to a `.env` file and run!

## Contributing

We'd love your help! Check out:

- **[CONTRIBUTING.md](https://github.com/willwoodward/woodwork-meta/blob/main/CONTRIBUTING.md)** - Contribution guidelines
- **[woodwork-language](https://github.com/willwoodward/woodwork-language)** - VSCode extension for `.ww` syntax highlighting
- **[woodwork-website](https://github.com/willwoodward/woodwork-website)** - Documentation website

## Roadmap

See the [roadmap](https://github.com/willwoodward/woodwork-meta/blob/main/ROADMAP.md) for planned features and improvements.

## License

woodwork-engine uses a GPL license, which can be read in full [here](./LICENSE).
