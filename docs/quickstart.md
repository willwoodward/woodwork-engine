---
title: Quickstart
description: A short, focused path to install and run Woodwork Engine in minutes.
index: 2
---

# Quickstart — 2 minute path

This guide gets you from install → runnable project quickly. Keep your `main.ww` small while you learn.

1. Install the package (stable release):

```bash
pip install woodwork-engine
```

2. Create a `.env` file in your project root (copy from `.env.example`) and set required keys (example for OpenAI):

```bash
cp .env.example .env
# then edit .env and add your key, e.g.:
# OPENAI_API_KEY=sk-...
```

3. Create a minimal `main.ww` in your project root. Use an LLM component (simplest path):

```
# main.ww

my_llm = llm openai {
  model: "gpt-4"
  api_key: "$OPENAI_API_KEY"
}

input = input command_line {
  to: my_llm
}
```

Notes:
- Property syntax in `.ww` uses colons (e.g., `model: "gpt-4"`).
- Environment variables are referenced with `$VARNAME` in `.ww` files.

4. Install runtime dependencies referenced by your config (run this after creating `main.ww`):

```bash
woodwork --init
```

5. Start Woodwork:

```bash
woodwork
```

You should be able to type into the command line and see responses from the configured LLM.

Quick tips:
- Keep examples small: start with a single LLM and a command-line input.
- For development, install editable/dev deps: `pip install -e .[dev]` and run `pytest` and `ruff format`.
- If using a hosted LLM, ensure your `.env` is present and contains the API key referenced in your `.ww`.

If something fails:
- Confirm `.env` exists and variables match what you referenced in `main.ww`.
- Check `examples/` for working configurations and copy the pattern.
