---
title: Quickstart
description: Get started with Woodwork Engine in minutes - from installation to your first running agent.
index: 0
---

# Quickstart

This guide gets you from installation to a running agent in under 5 minutes.

## Installation

Install Woodwork Engine via pip:

```bash
pip install woodwork-engine
```

This gives you access to the `woodwork` CLI tool.

## Setup

### 1. Create your configuration file

Create a `main.ww` file in your project directory. This is where you declare your agent components:

```ww
# main.ww - A simple Q&A agent

my_llm = llm openai {
  model: "gpt-4o-mini"
  api_key: $OPENAI_API_KEY
}

input = input command_line {
  to: my_llm
}
```

**Notes:**
- Properties use colon syntax: `model: "gpt-4o-mini"`
- Environment variables are referenced with `$VARNAME`

### 2. Set up environment variables

Create a `.env` file in your project root with your API keys:

```bash
# .env
OPENAI_API_KEY=sk-your-key-here
```

Make sure `.env` is in your `.gitignore` so API keys aren't committed.

### 3. Install dependencies

Install the dependencies your configuration needs:

```bash
woodwork --init
```

### 4. Run Woodwork

Start your agent:

```bash
woodwork
```

You should now be able to type messages and get responses from your LLM!

## Next Steps

Now that you have a working agent, check out:

- `docs/beginner-overview.md` - Understand the core concepts
- `docs/explanation/philosophy.md` - Learn why Woodwork uses Infrastructure as Code
- `docs/explanation/control-flow.md` - Master hooks and pipes for advanced control
- `examples/` - Working examples you can copy and adapt

## Troubleshooting

**Agent won't start:**
- Verify `.env` exists and contains the API keys referenced in `main.ww`
- Run `woodwork --init` to ensure all dependencies are installed

**Dependencies not installing:**
- Check that your `main.ww` file is valid
- Look at `examples/` for working configurations

**For development:**
- Install with dev dependencies: `pip install -e .[dev]`
- Run tests with `pytest`
- Format code with `ruff format`
