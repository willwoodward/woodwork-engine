---
title: Project Structure Overview
description: An overview of the package structure.
index: 0
---

### Running development scripts
This project uses ruff for linting and formatting, ty for static type checking, and pytest for unit tests. First, set up a development script with `uv venv`, then `source .venv/bin/activate`. Install the project as an editable package through `uv pip instal -e .`.

1. To run linter: `ruff check . --fix`
2. To run formatter: `ruff format .`
3. To run static type checking: `ty check .`
4. To run unit tests: `pytest tests/`
