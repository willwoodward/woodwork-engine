---
title: Beginner Overview
description: A short introduction to Woodwork Engine and its main components for new users.
index: 1
---

# Beginner Overview

Welcome to Woodwork Engine — a compact, modular framework for building AI agents and workflows using a single declarative configuration file (commonly `main.ww`).

This short guide focuses on what beginners actually need to know to get started.

## What you use as a beginner

- The `woodwork` CLI to start the program and interact with configured components.
- A configuration file (`main.ww`) that declares components (LLMs, inputs, outputs) and how they connect.
- A `.env` file for API keys and secrets referenced from the `.ww` config.

The basic flow for newcomers is: write a simple `.ww` config, add any required environment variables in `.env`, run `woodwork --init` to install runtime dependencies referenced by the config, then start `woodwork` and interact with your components.

## Minimal mental model

1. Declare components in `main.ww` (for example: an LLM and a command-line input).
2. The parser reads `main.ww` and instantiates the configured components.
3. Run `woodwork` to start the CLI and send inputs to the configured components.

Note: internal orchestration details (internal modules/classes) may change over time — beginners do not need to understand those internals to use the tool.

## Recommended next steps

1. Read docs/quickstart.md for a short install → run path.
2. Start with a single LLM and a command-line input in `main.ww`.
3. Explore `examples/` for working configurations you can copy.

## Where to contribute

- Add short, runnable tutorials to `docs/tutorials/`.
- Improve quickstart examples and `.ww` snippets to reduce friction for newcomers.

Thanks for improving the experience for new users — keeping docs short and focused helps people get productive faster.
