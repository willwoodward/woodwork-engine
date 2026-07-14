---
title: Config & Parsing
description: How .ww files are tokenized, resolved, and turned into Component objects
index: 1
---

# Config & Parsing

The config layer is responsible for turning a `.ww` text file into a dict of instantiated `Component` objects. It runs entirely before `asyncio.run()` — no event loop, no I/O.

## The .ww Syntax

Every declaration follows the same shape:

```ww
variable_name = component_type component_subtype {
    key: value
    other_key: $ENV_VAR
    dep_key: other_variable   # reference to another component
}
```

Example:

```ww
model = llm claude {
    model: "claude-sonnet-4-6"
    api_key: $ANTHROPIC_API_KEY
}

assistant = agent llm {
    model: model          # dependency — resolved to the model object above
    tools: [calendar]
}
```

## Pipeline: text → Component objects

```
get_declarations()          split text into (entry, line_number) pairs
      │
parse_component_declaration()   extract (variable, component, type)
parse_config()                  extract config dict + depends_on list
      │
command_checker()           validate no duplicate names, forbidden keywords
      │
dependency_resolver()       replace dep string names with actual objects
      │
create_object()             instantiate the correct Component subclass
      │
build_components()          collect into (list[Component], dep_map)
```

All of this lives in `woodwork/config/`.

## Step 1 — Tokenizing

`get_declarations()` in `woodwork/config/tokenizer.py` splits the raw `.ww` text into individual component blocks.

`parse_component_declaration()` extracts the three header tokens:
```python
variable = "assistant"
component = "agent"
type_     = "llm"
```

`parse_config()` reads the body `{ ... }` and returns:
- a flat `dict` of key/value pairs (strings, lists, or nested dicts)
- a `depends_on` list of variable names this component references

Environment variables (`$VAR`) are resolved via `python-dotenv` at this stage.

## Step 2 — Dependency Resolution

`dependency_resolver()` in `woodwork/config/resolver.py` is called once per component. It recursively walks the `depends_on` list and replaces string references in the config with the already-instantiated object.

For example, if `assistant` depends on `model`, the resolver calls `create_object()` for `model` first (if not already done), then sets `config["model"] = <ClaudeLLM instance>`.

This is how an `LLMAgent` receives a real `ClaudeLLM` object at construction time rather than a string name.

## Step 3 — Factory

`create_object()` in `woodwork/config/factory.py` is a large `if/elif` dispatch that maps `(component, type)` pairs to the right class:

```python
if component == "llm":
    if type_ == "claude":
        from woodwork.components.llms.claude import ClaudeLLM
        return init_object(ClaudeLLM, **config)
    if type_ == "openai":
        ...
if component == "agent":
    if type_ == "llm":
        from woodwork.components.agents.llm import LLMAgent
        return init_object(LLMAgent, **config)
```

`init_object()` checks that all required constructor parameters are present, raising `MissingConfigKeyError` with a clear message if not.

## Step 4 — build_components()

`build_components(declarations)` iterates the resolved commands dict and returns:

```python
components: list[Component]    # flat list, order doesn't matter yet
dep_map: dict[str, list[str]]  # name → [dependency names]
```

This is the output handed to `AsyncRuntime`. The runtime uses `dep_map` to topo-sort the startup order.

## The commands dict

Throughout the pipeline, each component is tracked as a dict:

```python
{
    "variable": "assistant",
    "component": "agent",
    "type": "llm",
    "config": { "model": <ClaudeLLM>, "tools": [...] },
    "depends_on": ["model", "calendar"],
    "object": <LLMAgent>,      # set after create_object()
}
```

## Adding a New Component Type

1. Create the class in `woodwork/components/<category>/mytype.py`, inheriting from `Component`.
2. Add an `if type_ == "mytype":` branch in `create_object()`.
3. Add a `format_kwargs()` call in `__init__` to normalize the config dict.

No changes needed to the parser, resolver, or runtime.
