---
title: Quickstart
description: A short, focused path to install and run Woodwork Engine in minutes.
index: 2
---

# Quickstart — 2 minute path

This quick guide gets you from nothing to a running Woodwork instance in a couple of minutes.

1. Install the package (stable release):

```bash
pip install woodwork-engine
```

2. Initialize the project (installs .ww dependencies):

```bash
woodwork init
```

3. Create a minimal `main.ww` in your project root. Example:

```
# main.ww

my_agent = agent openai {
  model = "gpt-4"
}

input = input.cli {}

pipeline = workflow {
  steps = [ input -> my_agent ]
}
```

4. Run Woodwork to load `main.ww` and start the CLI agent:

```bash
woodwork
```

You should see the agent start and the CLI prompt for input.

Quick tips:
- To work on docs or examples, clone the repo and use `pip install -e .[dev]` to install dev/test tools.
- Run tests with `pytest` and format with `ruff format` (requires `[dev]`).
- See `examples/` for runnable .ww files and `docs/tutorials/` for step-by-step guides.

If something fails, check `.env.example` for required environment variables (API keys, etc.) and read `docs/getting-started.md` for more setup details.
