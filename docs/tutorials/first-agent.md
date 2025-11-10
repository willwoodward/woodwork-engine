---
title: Your First Agent
description: Build a simple AI agent step-by-step
index: 0
---

# Tutorial: Build Your First Agent

Let's build a simple Q&A agent from scratch. This tutorial takes about 5 minutes.

## What We're Building

A command-line agent that:
- Accepts text input from the terminal
- Sends it to an OpenAI LLM
- Returns and logs the response
- Maintains no conversation history (stateless for simplicity)

## Step 1: Install Woodwork

```bash
pip install woodwork-engine
```

## Step 2: Create Your Project

```bash
mkdir my-first-agent
cd my-first-agent
```

## Step 3: Set Up API Key

Create a `.env` file with your OpenAI API key:

```bash
echo "OPENAI_API_KEY=sk-your-actual-key-here" > .env
```

**Important:** Add `.env` to your `.gitignore` so you don't commit secrets!

## Step 4: Write Your Agent Configuration

Create `main.ww`:

```ww
# Define the LLM component
my_llm = llm openai {
    model: "gpt-4o-mini"
    api_key: $OPENAI_API_KEY
}

# Define the input component and route to the LLM
input = input command_line {
    to: my_llm
}
```

**Let's break this down:**

**Line 2-5: Define the LLM**
- `my_llm` - A variable name you choose
- `llm openai` - Component type: an OpenAI LLM
- `model: "gpt-4o-mini"` - Which model to use
- `api_key: $OPENAI_API_KEY` - Reads from your `.env` file

**Line 8-10: Define the input**
- `input` - Variable name for the input component
- `input command_line` - Component type: command-line input
- `to: my_llm` - Route input to the LLM we defined above

That's it! Woodwork handles:
- Initializing the OpenAI client
- Managing the conversation flow
- Routing data between components
- Displaying the response

## Step 5: Install Dependencies

```bash
woodwork --init
```

This installs the packages your configuration needs (OpenAI SDK, etc.).

## Step 6: Run Your Agent

```bash
woodwork
```

You should see a prompt. Type a message:

```
> What is the capital of France?
```

The agent will respond:

```
The capital of France is Paris.
```

**Congratulations!** You just built your first AI agent with 7 lines of configuration.

## Step 7: Add Logging (Optional)

Let's add a hook to log all responses. Create `hooks/logging.py`:

```python
import logging

log = logging.getLogger(__name__)

def log_response(payload):
    """Log all LLM responses"""
    if isinstance(payload, dict):
        response = payload.get('data', payload)
        log.info(f"[Agent Response] {str(response)[:100]}...")
```

Update `main.ww` to use the hook:

```ww
my_llm = llm openai {
    model: "gpt-4o-mini"
    api_key: $OPENAI_API_KEY

    hooks = [
        { event: "llm.response_generated", function: "log_response", script: "hooks/logging.py" }
    ]
}

input = input command_line {
    to: my_llm
}
```

Run again:

```bash
woodwork
```

Now every response is logged! Check the logs directory for details.

## What's Happening Under the Hood?

When you type a message, here's what Woodwork does:

1. **Input component** captures your text
2. **Emits** `input.received` event with your text
3. **Routes** to `my_llm` (based on `to: my_llm`)
4. **LLM component** receives the event, calls OpenAI API
5. **Emits** `llm.response_generated` event
6. **Hook** (if configured) logs the response
7. **Output** automatically displays the response

All of this orchestration is automatic based on your `.ww` configuration.

## Next Steps

Now that you have a working agent, try:

**Add memory:**
```ww
mem = memory short_term {}

my_llm = llm openai {
    model: "gpt-4o-mini"
    api_key: $OPENAI_API_KEY
    memory: mem
}
```

**Add tools:**
```ww
calculator = api functions {
    path: "tools/calculator.py"
}

my_agent = agent llm {
    model: my_llm
    tools: [calculator]
}
```

**Explore more:**
- Check `examples/` for more complex agents
- Read `docs/explanation/control-flow.md` to master hooks and pipes
- See `docs/explanation/philosophy.md` to understand the IaC approach

## Common Issues

**"Command not found: woodwork"**
- Make sure you installed with `pip install woodwork-engine`
- Check that pip's bin directory is in your PATH

**"Missing API key"**
- Verify `.env` exists in the same directory as `main.ww`
- Check that the key in `.env` matches what you referenced in your config

**"Module not found" errors**
- Run `woodwork --init` to install dependencies

Ready to build something more complex? Check out the examples!
