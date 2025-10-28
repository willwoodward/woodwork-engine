---
title: Glossary
description: Common terms and short definitions to help beginners understand Woodwork Engine.
index: 4
---

# Glossary — quick reference

- .ww: The declarative configuration file format used by Woodwork Engine (e.g., `main.ww`). It declares components and how they connect.

- Component: A modular unit (LLM, agent, input, output, tool, etc.) defined in a .ww file and instantiated by the parser.

- Parser: The code that reads .ww files and instantiates configured components (see `woodwork/parser/config_parser.py`).

- Task Master: The orchestrator that manages workflows and component interactions (`woodwork/core/task_master.py`).

- Agent: A component that performs reasoning or decision-making, often backed by an LLM (e.g., `agent openai { ... }`).

- LLM: Large Language Model component (OpenAI, HuggingFace, etc.) used by agents to generate text.

- Knowledge Base (KB): A component that stores or indexes data for retrieval (e.g., Chroma, text files).

- Event: Typed messages exchanged between components (e.g., `input.received`, `agent.thought`). Events are JSON-serializable and typed in `woodwork/types/events.py`.

- Payload: Structured data carried by an event. Payload types are defined under `woodwork/types/` and validated by the PayloadRegistry.

- Hook: A read-only listener that runs when events occur (used for logging, monitoring). Hooks do not modify payloads.

- Pipe: A transform that runs sequentially on an event and can modify its payload before it continues through the system.

- Workflow / Pipeline: A configured flow connecting components so events move from inputs → agents → outputs/tools.

- CLI Input: The built-in command-line input component used for quick local testing (`input.cli`).

- Example / examples/: Directory with runnable .ww examples. Copying and adapting these is the fastest way to learn.

- main.ww: Common filename used as the primary entrypoint configuration for a Woodwork project.

# Where to learn more
- Quickstart: docs/quickstart.md — the shortest path from install → running an agent.
- Beginner overview: docs/beginner-overview.md — architecture summary and next steps.
- Tutorials: docs/tutorials/first-project.md — minimal walkthrough creating and running a tiny project.

If a term here is unclear or missing, please open a PR to expand this glossary — small clarifications help new contributors a lot.
