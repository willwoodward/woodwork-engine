---
title: Agent Execution
description: How LLMAgent and AgentLoop implement the ReAct reasoning loop
index: 4
---

# Agent Execution

Agent execution is split across two classes with distinct responsibilities:

| Class | File | Responsibility |
|-------|------|---------------|
| `LLMAgent` | `components/agents/llm.py` | Component wrapper — owns event bus, tools, features |
| `AgentLoop` | `components/agents/agent_loop.py` | Pure ReAct loop — no Component base, no sessions |

This separation makes the loop easy to test in isolation and the agent easy to swap out.

## LLMAgent.execute()

The entry point for running an agent:

```python
await agent.execute("run", {"query": "What's on my calendar?", "session_id": "abc"})
```

It does four things:

1. Builds an `AgentContext` from the inputs
2. Builds a `ToolRegistry` from its tool list + any feature-provided tools
3. Builds the system prompt (current date + tool docs + prompt file)
4. Creates an `AgentLoop` and delegates to `loop.run(ctx, system_prompt)`

The `ToolRegistry` is rebuilt on every call so dynamically-added tools from internal features are always current.

## AgentContext

```python
@dataclass
class AgentContext:
    query: str
    session_id: str
    inputs: dict         # extra inputs from the caller
    history: list        # Message objects (for future use)
    steps: list          # Step objects recorded during this run
    variables: dict      # named outputs stored across steps
```

`variables` is used for inter-step data: if a tool call specifies `output: "my_var"`, its result is stored in `ctx.variables["my_var"]` and can be referenced as an input to a later tool call.

## The ReAct Loop

`AgentLoop.run()` implements Reasoning + Acting:

```
for iteration in range(25):
    raw = await llm.call(system_prompt, "", current_prompt)
    thought, action_dict, is_final = _parse(raw)

    if is_final:
        return thought                         # done

    if action_dict is None:
        consecutive_no_action += 1
        if consecutive_no_action >= 3:
            return thought                     # force answer
        prompt LLM to act next iteration
        continue

    observation = await registry.execute(tool, action, inputs)
    append (thought, action, observation) to current_prompt
    continue
```

Hard limits: 25 iterations, 90,000 tokens. If context grows too large it's summarised via the LLM before the next iteration.

## Parsing LLM Output

The LLM is prompted to produce ReAct-formatted output:

```
Thought: I need to check the user's calendar.
Action: {"tool": "calendar", "action": "list_events", "inputs": {"date": "today"}}

OR:

Thought: The user has three meetings today.
Final Answer: You have three meetings today: standup at 9am, ...
```

`_parse(raw)` extracts these with regex. `_extract_json_object()` handles the Action JSON using balanced-brace extraction (more robust than regex for nested JSON).

## Tool Calls

`ToolRegistry.execute(name, action, inputs)` dispatches to `tool.execute(action, inputs)`. All tools are `Component` subclasses registered by the factory.

**Local tools** (Functions, Web, CommandLineTool) run in-process.

**MCP tools** (MCPServer) communicate over HTTP or stdio to an external process. `MCPServer.execute()` sends a JSON-RPC `tools/call` message over the established channel and awaits the response.

Variable references in inputs are resolved before the call:

```python
# .ww config might produce:
{"tool": "search", "inputs": {"query": "search_result"}}

# If ctx.variables["search_result"] = "Paris weather"
# _resolve_vars() turns this into:
{"query": "Paris weather"}
```

## LLM Interface

All LLM classes implement:

```python
async def call(self, system_prompt: str, history: str, query: str) -> str
```

`AgentLoop` calls this directly — no tool routing, no event bus. The LLM returns a plain string. This simplicity is intentional: the loop owns the ReAct structure; the LLM just completes text.

Internally, each LLM wraps a LangChain chat model:

```python
# BaseLLM.call()
prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("human", "{input}"),
])
chain = prompt | self._llm
return chain.invoke({"input": query}).content
```

## Event Emissions During Execution

```
agent.thought       after every non-final thought
agent.action        before every tool call (pipes can transform the action)
tool.call           with tool name + args
tool.observation    with tool name + result
agent.step_complete after each iteration
agent.error         if a tool raises an exception
```

These emit on the agent's per-agent `EventBus`, which bubbles to the system bus. See `06-observability.md`.

## Internal Features

`LLMAgent` supports **internal features** — optional capabilities attached at the agent level (currently: workflow caching via Neo4j). Features can:

- Register additional tools into the registry via `get_tools()`
- Hook into the agent's event bus
- Persist/retrieve state via `InternalComponentManager`

Features are declared in the `.ww` config and wired during `start()`.
