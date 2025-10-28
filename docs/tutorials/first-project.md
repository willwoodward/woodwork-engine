---
title: First Project (Beginner Tutorial)
description: A minimal, hands-on tutorial showing how to create and run a tiny Woodwork project using main.ww.
index: 3
---

# First Project — Minimal Example

This short tutorial walks you through creating a minimal `main.ww` and running Woodwork locally.

Goal: get a simple agent running that echoes CLI input.

## Files you'll create

- main.ww — a minimal configuration that wires a CLI input to a simple echo agent

## Example main.ww

```
# main.ww

# A tiny 'echo' agent that returns the input as output
my_agent = agent simple {
  # 'simple' agent is illustrative — replace with a real agent component like openai in real projects
  behavior = "echo"
}

input = input.cli {}

pipeline = workflow {
  steps = [ input -> my_agent ]
}
```

Notes:
- The `agent simple` block is a minimal placeholder. Real usage will use components such as `agent openai { model = "gpt-4" }` and require API keys.
- This example is intended to show the wiring approach: declare components, then a workflow that connects them.

## Run the project

1. Install the package (or use editable installs while developing):

```bash
pip install -e .[dev]
```

2. Put `main.ww` (from above) into your project root.

3. Initialize (installs optional runtime dependencies referenced by .ww files):

```bash
woodwork init
```

4. Start Woodwork:

```bash
woodwork
```

5. Type input into the CLI — the echo agent should return your input.

## If it doesn't work

- Check `.env.example` and set any required environment variables (e.g., API keys) in `.env`.
- If you used a real agent (OpenAI), make sure your API key is set and the component name matches a supported component (see `woodwork/components/`).
- For development, run tests with `pytest` and formatting with `ruff format`.

## Next steps

- Replace the simple agent with `agent openai { model = "gpt-4" }` (requires API key).
- Inspect `examples/` for real, runnable .ww files and copy patterns into your own projects.
- Read docs/quickstart.md and docs/beginner-overview.md for more context.
