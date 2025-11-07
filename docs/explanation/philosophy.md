---
title: Philosophy
description: Why Woodwork uses Infrastructure as Code for AI agents
index: 0
---

# Philosophy: Why Infrastructure as Code for AI Agents?

## The Problem

Building AI agents is harder than it should be. Every project starts the same way:

- Copy-paste boilerplate for LLM integration
- Wire up tools, memory, and knowledge bases manually
- Write orchestration logic to connect everything
- Maintain brittle glue code as requirements change

By the time you have a working agent, you've written hundreds of lines of infrastructure code that has nothing to do with your actual use case. Worse, when you need to build a second agent, you start from scratch again.

## The IaC Solution

Infrastructure as Code (IaC) transformed how we deploy servers, databases, and cloud resources. Instead of writing scripts to provision infrastructure, we declare what we want in configuration files (Terraform, Kubernetes, etc.) and let the platform handle the details.

Woodwork applies this same principle to AI agents.

**Instead of this (imperative):**
```python
# 50+ lines of setup code
llm = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
memory = ConversationMemory()
tools = [WebSearch(), Calculator()]
agent = Agent(llm=llm, memory=memory, tools=tools)

# Complex orchestration
while True:
    user_input = input("> ")
    context = memory.get_context()
    response = agent.run(user_input, context)
    memory.store(user_input, response)
    print(response)
```

**You write this (declarative):**
```ww
my_agent = agent llm {
    model: language_model
    memory: conversation_memory
    tools: [web_search, calculator]
}

input = input command_line {
    to: my_agent
}
```

Woodwork handles orchestration, tool routing, memory management, and component lifecycle automatically.

## Why This Matters

**1. Reproducibility**
Your agent configuration is code. Check it into git. Deploy it anywhere. No hidden state, no manual setup steps.

**2. Modularity**
Components are self-contained and reusable. Build a knowledge base once, use it across multiple agents. Swap out an OpenAI LLM for Ollama with one line change.

**3. Rapid Iteration**
Want to add a new tool? Add one line to your `.ww` file. Want to experiment with different LLMs? Change the `model:` property. No refactoring required.

**4. Focus on Value**
Stop writing infrastructure code. Focus on your domain: the tools your agent needs, the prompts that drive behavior, the workflows that deliver value.

## The Woodwork Approach

Woodwork treats agent components as declarative building blocks:

- **LLMs**: OpenAI, Ollama, HuggingFace - just specify which one
- **Memory**: Short-term, vector databases, graph databases - pick what fits
- **Tools**: APIs, functions, command-line tools - connect them in seconds
- **I/O**: CLI, voice, streaming - use what makes sense

Under the hood, Woodwork handles:
- Component initialization and lifecycle
- Event routing and orchestration
- Tool invocation and response handling
- Session management and state

You get production-grade agent infrastructure without writing the infrastructure.

## When to Use Woodwork

Woodwork excels at:
- **Vertical agents**: Task-specific agents (customer support, data analysis, coding assistants)
- **Rapid prototyping**: Test ideas in minutes, not hours
- **Production deployment**: Reproducible, version-controlled agent configs

## The Result

With Infrastructure as Code for agents, you get:
- **Less code**: 10 lines of config instead of 200 lines of Python
- **More clarity**: Your `.ww` file documents exactly how your agent works
- **Faster iteration**: Change configuration, not code
- **Production ready**: Built-in session management, event handling, and error recovery

Declare what you want. Woodwork handles how to build it.
