---
title: Your First Agent
description: Build a simple AI agent step-by-step
index: 0
---

# Tutorial: Build Your First Agent

Let's build a simple Q&A agent from scratch. This tutorial takes about 5 minutes. Example code will be in the examples/ directory.

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
    model: "gpt-5-mini"
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
- `model: "gpt-5-mini"` - Which model to use
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

Ready to build something more complex? Check out the examples!
