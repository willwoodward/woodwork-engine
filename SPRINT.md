# Woodwork Engine — 1 Month Sprint

## Vision

An **open source, self-hostable, IaC-configured AI agent runtime** with context-first middleware. The only agent framework where you own the entire execution path — no proprietary cloud required.

**The differentiators:**
- `.ww` declarative config + Python-native API (both surfaces, one runtime)
- Context-first hooks and pipes — middleware that sees the full conversation trajectory, not just isolated events
- Pipes as control flow operators (`Halt`, `Retry`, `Spawn`) — not just transformers
- `woodwork build` → Dockerfile → deploy to any cloud
- Genuinely open. No Bedrock, no Cloud Run, no OpenAI infrastructure required.

---

## Architecture Principles

**Three concerns, cleanly separated:**

```
Tool execution    →  direct async function calls (not through event bus)
Observability     →  hooks and pipes wrap execution as middleware
Workflow caching  →  WorkflowRecorder as a passive hook, saves to Neo4j
```

**Pipe return types:**
```python
PipeResult = Payload | Halt | Retry | Spawn
```
The agent's execution path stays simple and linear. Pipes govern behaviour. The agent reasons.

**Two surfaces, one implementation:**
```
Python API  →  the only real implementation
.ww files   →  thin config layer, parser emits Python API calls
```

---

## Week 1 — Foundation

> Goal: clean execution path and Python API. Everything else sits on this.

**Day 1 — Design the Python API surface**
Write the API on paper before touching code. What does the simplest agent look like? The most complex? Lock in `Agent`, `LLM`, `mcp()`, `@hook`, `@pipe`, `@pipe` return types. Get this right first.

**Day 2-3 — `AgentContext` as a first-class object**
Replace `current_prompt` string accumulation with a structured object:
```python
@dataclass
class AgentContext:
    session_id: str
    query: str
    steps: list[Step]
    variables: dict[str, Any]
    iteration: int
```
Every `emit()` call passes context alongside payload. This is what hooks and pipes receive.

**Day 4-5 — Clean execution path**
- Tools called directly as async functions, not through event bus
- Event bus becomes purely middleware (hooks/pipes/events)
- Delete `TaskMaster`, replace with `WorkflowRecorder` as a passive hook
- `UnifiedEventBus` slimmed to only hooks, pipes, events

---

## Week 2 — The Differentiators

> Goal: ship the things nobody else has.

**Day 6-7 — Context-first hooks and pipes**
- `@hook("agent.thought")` receives `(payload, context)`
- `@pipe("agent.thought")` receives `(payload, context)`, returns `PipeResult`
- Implement `Halt`, `Retry`, `Spawn` directives
- Execution loop handles each directive type
- Write 3-4 reference implementations: loop detection, context compression, approval gate, persona enforcement

**Day 8-9 — Multi-agent**
- Day 8: agent-as-tool (`tools=[researcher_agent]`)
- Day 9: handoffs (agent passes control to another agent)

**Day 10 — `.ww` as thin translation layer**
Refactor parser to emit Python API calls instead of directly instantiating components. Both surfaces verified working and in sync automatically.

---

## Week 3 — Make it Shippable

> Goal: production-credible and deployable.

**Day 11 — Structured outputs**
JSON schema support on `Agent`. Every serious use case needs this.

**Day 12 — Human-in-the-loop**
Clean API for pausing execution. Implemented as a `Halt`-returning pipe — validates the control flow model works end-to-end.

**Day 13 — Session persistence**
Conversations survive restarts. SQLite by default, pluggable backends.

**Day 14 — Guardrails**
Input/output validation declarable on `Agent` or as a `@pipe`. Enterprise checkbox feature.

**Day 15 — `woodwork build`**
Generates:
- `Dockerfile` — agent containerised, production-ready, entry point inferred from input type
- `docker-compose.yml` — with any required sidecars (Neo4j if caching enabled)
- `.env.example` — auto-generated from every `$VARIABLE` reference in the agent definition

Deploy to any cloud that runs Docker.

---

## Week 4 — Getting Started Experience

> Goal: a developer hits a working agent in under 5 minutes.

**Day 16 — Fully local Ollama example**
One complete example: Ollama + Woodwork, zero external API calls, zero cloud. First-class README. Underserved audience, nobody else has a clean story here.

**Day 17 — `woodwork new` scaffolding**
```bash
woodwork new my-agent --template life-assistant
```
Generates a working Python file, `.env.example`, folder structure. Removes the blank page problem.

**Day 18 — Error messages**
Parser errors, missing env vars, undefined components — all human-readable with suggestions. Unsexy but what makes or breaks first impressions.

**Day 19 — Getting started guide**
The only doc that matters this month. Developer with no prior knowledge → working agent in 5 minutes. Covers Python API and `.ww` config.

**Day 20 — Buffer**
Something will slip. Use this.

---

## Building With It

**Start using Woodwork to build your own agents from day one of the sprint — not after.**

Every time you hit friction, fix the framework before continuing. The agents you build become your best documentation, your best demos, and your best evidence it works. A life assistant you actually use daily is more compelling than any README.

Target: end of the month with a polished framework *and* 2-3 real agents in daily use.

---

## What You Have at the End

```bash
pip install woodwork-engine
woodwork new life-assistant
# edit 30 lines of Python
woodwork build
docker run --env-file .env life-assistant
```

A developer goes from zero to a running multi-agent system in under an hour, deployable to any cloud they already use, with no proprietary runtime dependencies.

That's the thing developers write about.
