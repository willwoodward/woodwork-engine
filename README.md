[![PyPI - Version](https://img.shields.io/pypi/v/woodwork-engine.svg?logo=pypi&label=PyPI&logoColor=gold)](https://pypi.org/project/woodwork-engine/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/woodwork-engine.svg?logo=python&label=Python&logoColor=gold)](https://pypi.org/project/woodwork-engine/)
[![PyPI - Installs](https://img.shields.io/pypi/dm/woodwork-engine.svg?color=blue&label=Installs&logo=pypi&logoColor=gold)](https://pypi.org/project/woodwork-engine/)
[![License](https://img.shields.io/github/license/willwoodward/woodwork-engine?label=License&logo=open-source-initiative)](https://github.com/willwoodward/woodwork-engine/blob/main/LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/willwoodward/woodwork-engine?label=Stars&logo=github)](https://github.com/willwoodward/woodwork-engine/stargazers)

# woodwork-engine
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
1. **Create a main.ww file and write some code**: This file is where component declarations are read from. For some inspiration, consult the examples
2. **Run `woodwork init`**: This installs the necessary dependencies to run your components
3. **Run `woodwork`**: This activates the components

## Examples
For some examples, consult the examples folder. ENV variables are denotes by a '$', place a .env file in the same directory as the main.ww file and populate it with the necessary variables.

## Contributing
To view the contributing guide for woodwork, the [CONTRIBUTING.md](https://github.com/willwoodward/woodwork-meta/blob/main/CONTRIBUTING.md) file in the meta repository contains more information. We would love your help! Additionally, if you prefer working on other projects aligned with language servers or web development, [woodwork-language](https://github.com/willwoodward/woodwork-language) and [woodwork-website](https://github.com/willwoodward/woodwork-website) could be worth taking a look at.

## License
woodwork-engine uses a GPL license, which can be read in full [here](./LICENSE).

