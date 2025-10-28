---
title: Beginner Overview
description: A short introduction to Woodwork Engine and its main components for new contributors.
index: 1
---

# Beginner Overview

Welcome to Woodwork Engine — a lightweight, modular framework for building AI agents and workflows using a declarative `.ww` configuration language.

This short guide gives you the essentials to get started and points to the next steps.

## What is Woodwork Engine?

- A CLI-driven tool (`woodwork`) that loads `.ww` configuration files describing components and workflows.
- Components are modular (LLMs, knowledge bases, inputs, outputs, tools) and connected via an event system.
- Designed to be extensible: add new components, hooks, pipes, and payload types.

## High-level architecture

- Parser: `woodwork/parser/config_parser.py` — reads `.ww` files and creates component instances.
- Core/Task Master: `woodwork/core/task_master.py` — orchestrates tasks and component interactions.
- Components: `woodwork/components/` — implementations for LLMs, KBs, agents, inputs, outputs, etc.
- Event system: `woodwork/events/` and `woodwork/types/events.py` — typed, JSON-serializable events, hooks, and pipes.
- Types: `woodwork/types/` — central place for payloads, prompts, and type definitions.

## Quick mental model

1. You write a `.ww` file declaring components and how they connect.
2. The parser instantiates components and wires them into the Task Master.
3. Events flow between components (hooks for logging, pipes for transforms).
4. Agents and tools call actions; the event system ensures typed payloads and attribution.

## Recommended next steps

1. Read docs/getting-started.md for installation and basic usage.
2. Try an example `.ww` from `examples/` to see components wired together.
3. Read docs/tutorials/first-project.md (coming) for a minimal hands-on walkthrough.
4. Explore `woodwork/components/` and `woodwork/types/` to learn extension points.

## Where to contribute

- Add beginner-friendly tutorials in `docs/tutorials/` (short, runnable examples).
- Improve docs/quickstart.md with a 2–3 minute path from install → run.
- Add more explicit examples for common components under `examples/`.

Thanks for helping make Woodwork Engine easier for beginners — small, clear docs make a big difference!
