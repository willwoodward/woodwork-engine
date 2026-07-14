---
title: Architecture Overview
description: High-level map of how Woodwork turns a .ww file into a running agent
index: 0
---

# Architecture Overview

Woodwork turns a declarative `.ww` configuration file into a running multi-component AI system. There are three phases and three layers.

## The Three Phases

```
Phase 1 — Parse     .ww text → Component objects
Phase 2 — Start     Component objects → initialized, connected services
Phase 3 — Run       AsyncRuntime drives the input/agent loop until shutdown
```

These phases are sequential and visible in `woodwork/cli/main.py`:

```python
components, dep_map = parse_and_validate_config()   # Phase 1
start_components(components)                         # Phase 2
start_runtime(components, dep_map)                   # Phase 3
```

## The Three Layers

| Layer | What it does | Key files |
|-------|-------------|-----------|
| **Config** | Parses `.ww` text, resolves dependencies, instantiates components | `woodwork/config/` |
| **Components** | Self-contained units of capability (LLMs, tools, inputs, agents) | `woodwork/components/` |
| **Runtime** | Lifecycle orchestration, main loop, graceful shutdown | `woodwork/core/runtime.py` |

## End-to-End Data Flow

```
main.ww
   │
   ▼ tokenizer → resolver → factory
Component objects  (LLMAgent, MCPServer, CommandLineInput, ClaudeLLM …)
   │
   ▼ AsyncRuntime._start_all()
Started components  (aiohttp sessions open, LLM clients ready …)
   │
   ▼ AsyncRuntime._run_cli()
Loop:
  user types query
    → CommandLineInput.stream() yields it
    → LLMAgent.execute("run", {"query": ...})
        → AgentLoop.run(ctx, system_prompt)
            → LLM.call()  ←→  Tool.execute()  (repeat)
            → returns final answer string
    → CommandLineInput.respond(answer)
  repeat
   │
   ▼ Ctrl+C
AsyncRuntime._cleanup()  →  Component.stop() for each component
```

## Key Design Decisions

**Components are plain objects.** There is no global message bus. A component receives inputs through direct method calls and returns outputs as return values.

**AgentLoop is pure.** All ReAct logic lives in `woodwork/components/agents/agent_loop.py`. It has no Component base class, no session management, no event bus wiring — those belong to `LLMAgent`.

**EventBus is for observability, not routing.** Events (hooks, pipes) fire around tool calls and LLM responses so you can log, debug, or transform data. They do not replace direct function calls.

**Dependency injection via the config layer.** When component A depends on component B, the resolver replaces the string name `"B"` in A's config with the actual B object before A is instantiated.

## Directory Map

```
woodwork/
  cli/            CLI entrypoint, progress bars, shutdown
  config/         .ww parser, resolver, factory
  core/           Runtime, EventBus, ToolRegistry, core types
  components/
    agents/       LLMAgent, AgentLoop
    llms/         OpenAI, Claude, Ollama, HuggingFace
    inputs/       CommandLineInput, APIInput
    apis/         Functions, Web
    mcp/          MCPServer (MCP protocol integration)
    knowledge_bases/  Chroma, Neo4j, TextFile
    memory/       ShortTermMemory
    outputs/      Voice
    environments/ Coding (Docker)
  interfaces/     Stoppable, Startable, tool_interface
  deploy/         Docker deployment, router
  types/          Data types (events, workflows, prompts)
```

## Where to Go Next

- **Config parsing in detail** → `02-config-and-parsing.md`
- **Component lifecycle** → `03-component-lifecycle.md`
- **Runtime orchestration** → `04-runtime.md`
- **Agent execution (ReAct loop)** → `05-agent-execution.md`
- **Observability (EventBus)** → `06-observability.md`
