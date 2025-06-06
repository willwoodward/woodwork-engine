# woodwork-engine

[![PyPI - Version](https://img.shields.io/pypi/v/woodwork-engine.svg?logo=pypi&label=PyPI&logoColor=gold)](https://pypi.org/project/woodwork-engine/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/woodwork-engine.svg?logo=python&label=Python&logoColor=gold)](https://pypi.org/project/woodwork-engine/)
[![PyPI - Installs](https://img.shields.io/pypi/dm/woodwork-engine.svg?color=blue&label=Installs&logo=pypi&logoColor=gold)](https://pypi.org/project/woodwork-engine/)
[![License](https://img.shields.io/github/license/willwoodward/woodwork-engine?label=License&logo=open-source-initiative)](https://github.com/willwoodward/woodwork-engine/blob/main/LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/willwoodward/woodwork-engine?label=Stars&logo=github)](https://github.com/willwoodward/woodwork-engine/stargazers)

Welcome to woodwork-engine, an AI Agent IaC tool that aims to make developing and deploying AI Agents easier.

Through defining components in a configuration language, an LLM will decompose the task into actionable steps, which can be executed using the supplied tools. We use latest research to inform design decisions, and we implement this as most of the setup is copy/paste across projects. Through only focussing on the necessary components of a system, this package should make designing custom, vertical agents much easier.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Examples](#examples)
- [Contributing](#contributing)
- [License](#license)

## Features

- A custom config language, woodwork (.ww files), allowing agent components to be declared
- Integrations and communication between components are handled
- Additional customisation or extension can be provided by implementing some of our interfaces

![Screenshot 2025-01-01 160031](https://github.com/user-attachments/assets/1a1c759e-aa5e-4499-902f-6d8abd23b3b8)

A [roadmap](https://github.com/willwoodward/woodwork-meta/blob/main/ROADMAP.md) is provided with details on future features.

## Installation

1. **Run `pip install woodwork-engine`**: This gives access to the `woodwork` CLI tool, along with the ability to parse and deploy AI Agent components from .ww files
2. **Install the Woodwork extension on VSCode if relevant**: This provides syntax highlighting and intellisense for code in .ww files

## Usage

1. Begin by duplicating the [`.env.example`](./woodwork/config/) file and placing it in your project's root directory
1. Rename the file to `.env` (ensure this is part of your project's `.gitignore` so that it isn't committed)
1. Depending on the `.ww` configuration file, populate the `.env` file with your corresponding keys

See the `.env.example` file for further details.

Once you've configured your `.ww` config file and your `.env` file, there are two ways to run `woodwork`: A standalone application, or used as a dependency.

### Standalone Application

1. **Create a main.ww file and write some code**: This file is where component declarations are read from. For some inspiration, consult the examples
1. **Run `woodwork init`**: This installs the necessary dependencies to run your components
1. **Run `woodwork`**: This activates the components and initializes a logger

### As A Dependency

When using `woodwork` as a dependency, you will need to build your own logger implementation. Not building your own logger will result in no logs being generated but the application will still run.

1. (Optional) **Create a `./config` directory**: This is where the logging configuration will live.
1. (Optional) **Copy the [`log_config.json`](./woodwork/config/log_config.json) into your `./config` directory**: This configures your logger
1. In your file you'd like to utilize `woodwork` in, add `from woodwork import __main__ as m`
1. See [`dev-main.py`](./dev-main.py) for how to build your logger and configure calling `woodwork`

## Developer Setup

If you are interested in contributing, the following steps are used to activate a developer environment.

1. Install `pre-commit` if needed via `pip install pre-commit`
1. Run `pre-commit install [--hook-type pre-push]` to run linting and formatting before commiting or pushing

## Available Arguments

You can pass arguments to `woodwork`. For more details, see `woodwork --help`.

|Argument|Options|Default|Notes|
|-|-|-|-|
|`--mode`|`run`, `debug`, `embed`, `clear`|`run`|Debug is deprecated, use Run instead. If using a workflow, you must use `embed` or `clear`.|
|`--init`|`none`, `isolated`, `all`|`none`||
|`--workflow`|`none`, `add`, `remove`, `find`|`none`|If specifying a workflow, you must provide a target.|
|`--target`|String|`""`|Defines the target for the workflow. For add workflows, specify the file path to the workflow. For `remove` workflows, specify the workflow ID. For `find` workflows, specify the search query.|
|`--version`|N/A|N/A|Prints the current version of Woodwork. Note: this will override any other arguments.|

When calling your script, you can pass argument to the script as long as they do not conflict with `woodworks` arguments.

## Logging

In `log_config.json`, you can set the desired logging levels for stdout and the generated log file. Do this by editing the respective `level` property in the json for the respective handler. Options include the standard logging levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.

You can monitor the log file during execution by opening a terminal and entering `tail -f logs/debug_log.log` (or your custom log file name if modified in the `log_config.json`)

## Examples

For some examples, consult the examples folder. ENV variables are denotes by a '$', place a .env file in the same directory as the main.ww file and populate it with the necessary variables.

## Contributing

To view the contributing guide for woodwork, the [CONTRIBUTING.md](https://github.com/willwoodward/woodwork-meta/blob/main/CONTRIBUTING.md) file in the meta repository contains more information. We would love your help! Additionally, if you prefer working on other projects aligned with language servers or web development, [woodwork-language](https://github.com/willwoodward/woodwork-language) and [woodwork-website](https://github.com/willwoodward/woodwork-website) could be worth taking a look at.

## License

woodwork-engine uses a GPL license, which can be read in full [here](./LICENSE).
