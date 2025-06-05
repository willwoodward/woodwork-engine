---
title: Introduction
description: An introduction to creating your first AI application using woodwork-engine.
index: 0
---

# Background
`woodwork-engine` was created to make the development and deployment of AI solutions, in particular LLM agents, more simple. Instead of writing hundreds of lines of Python code to achieve largely similar functionality across different projects, we provide a configuration language that is quick and easy to use.

If you haven't already, I'd recommend checking out the [Getting Started](https://woodwork-engine.com/docs/getting-started) guide to get `woodwork-engine` set up.

# Configuring an LLM
An initial starting point is to set up a connection with an LLM. In this guide, we will be using `gpt-4o-mini` from OpenAI, but feel free to check out our documentation for support on local and online models.

To begin, create a new directory for your project, and `cd` into this directory. Create a `main.ww` file and add the following code:

```woodwork
my_llm = llm openai {
    model: "gpt-4o-mini"
    api_key: $OPENAI_API_KEY
}
```

Lets explain this line-by-line. We first begin by assigning our llm to a variable name, `my_llm`. We then specify that this is an `llm`  **component**, of **type** `openai`. We support many other LLM component types, such as `hugging_face`.

The content inside the curly braces is reffered to as the component's **configuration**. We can use the `model` key to specify the model, with names of supported models found on their [documentation](https://platform.openai.com/docs/models). The `api_key` key references the environment variable called `OPENAI_API_KEY`.

### Adding the OpenAI API Key
Create an account on the [OpenAI Developer Platform](https://platform.openai.com/), and create a new project. Create a new read-only secret key on the [API Keys Page](https://platform.openai.com/settings/organization/api-keys). Copy the secret key and place it into the `.env` file in the same directory as your `main.ww` file:

```
OPENAI_API_KEY=...
```

Note that this file should **never** be exposed publicly. Make sure to add some money to your OpenAI account.

### Interacting with the LLM
Now we have defined the LLM, we need some way of sending inputs and receiving outputs. This can be done simply using the `command_line` `input`. Add the following line of code to your `main.ww` file:

```woodwork
input = input command_line {
    to: my_llm
}
```

This creates the `command_line` input, and references the variable `my_llm` as input to.

# Running Locally
To run, simply type `woodwork` in your terminal. This will install all the necessary packages, and deploy the components. Keep in mind that inference with OpenAI LLMs will cost money, make sure to consult their pricing.

### Final Code
```woodwork
my_llm = llm openai {
    model: "gpt-4o-mini"
    api_key: $OPENAI_API_KEY
}

input = input command_line {
    to: my_llm
}
```
