import inspect
import json
import logging
import os
import re

from dotenv import load_dotenv
from typing import Any

from woodwork.components.task_master import task_master
from woodwork.errors import (
    ForbiddenVariableNameError,
    MissingConfigKeyError,
)
from woodwork.registry import get_registry

log = logging.getLogger(__name__)

task_m = task_master(name="task_master")


def resolve_dict(dictionary, dependency, component_object):
    # Modify the value to be the object
    for key, value in dictionary.items():
        if value == dependency:
            dictionary[key] = component_object
        elif isinstance(value, dict):
            resolve_dict(value, dependency, component_object)


def dependency_resolver(commands, component):
    # Parser parses into JSON for each component
    # Each component should have a 'depends_on' array if it uses a variable as a value, init as []
    # How do we get each variable? Dict of commands, key = name, value = component dictionary
    # Traverse the depends_on as DFS

    log.debug(component)
    # Base case: no dependencies in the depends_on array
    if component["depends_on"] == []:
        # Initialise component, return object reference
        if "object" not in component:
            component["object"] = create_object(component)
        return component["object"]

    # Else, if the depends_on array has dependencies
    for dependency in component["depends_on"]:
        # Resolve that dependency, replace those variables in the config
        component_object = dependency_resolver(commands, commands[dependency])

        for key, value in component["config"].items():
            # Handle arrays
            if isinstance(value, list):
                for i in range(len(value)):
                    if value[i] == dependency:
                        value[i] = component_object

            # Handle dictionaries
            if isinstance(value, dict):
                resolve_dict(value, dependency, component_object)

            if value == dependency:
                log.debug("Value: %s; Dependency: %s", value, dependency)
                component["config"][key] = component_object

    # Return component object
    component["depends_on"] = []
    component["object"] = create_object(component)
    return component["object"]


def get_required_args(cls):
    """
    Gets the required arguments for the class constructor and all parent classes,
    excluding the class named 'component'.
    """
    required_args = []

    # Traverse the MRO and skip the class named 'Component'
    for base in inspect.getmro(cls):
        if base.__name__ == "component":
            continue  # Skip 'Component' class
        constructor = inspect.signature(base.__init__)
        for name, param in constructor.parameters.items():
            if (
                param.default is inspect.Parameter.empty
                and param.kind
                in (
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    inspect.Parameter.KEYWORD_ONLY,
                )
                and name != "self"
            ):
                required_args.append(name)

    return list(set(required_args))


def init_object(cls, **params):
    required_args = get_required_args(cls)

    for param in list(params.keys()):
        if param in required_args:
            required_args.remove(param)

    if len(required_args) == 1:
        raise MissingConfigKeyError(
            f'Key "{required_args[0]}" missing from {cls.__name__}.',
        )

    if len(required_args) > 1:
        raise MissingConfigKeyError(
            f"Keys {required_args} missing from {cls.__name__}.",
        )

    return cls(**params)


def create_object(command):
    component = command["component"]
    type = command["type"]
    variable = command["variable"]
    config = command["config"].copy()

    # Add metadata to the config
    config["name"] = variable

    if component == "knowledge_base":
        if type == "chroma":
            from woodwork.components.knowledge_bases.vector_databases.chroma import (
                chroma,
            )

            return init_object(chroma, **config)
        if type == "neo4j":
            from woodwork.components.knowledge_bases.graph_databases.neo4j import neo4j

            return init_object(neo4j, **config)
        if type == "text_file":
            from woodwork.components.knowledge_bases.text_files.text_file import (
                text_file,
            )

            return init_object(text_file, **config)

    if component == "memory":
        if type == "short_term":
            from woodwork.components.memory.short_term import short_term

            return init_object(short_term, **config)

    if component == "llm":
        if type == "hugging_face":
            from woodwork.components.llms.hugging_face import hugging_face

            return init_object(hugging_face, **config)
        if type == "openai":
            from woodwork.components.llms.openai import openai

            return init_object(openai, **config)
        if type == "ollama":
            from woodwork.components.llms.ollama import ollama

            return init_object(ollama, **config)

    if component == "input":
        if type == "keyword_voice":
            from woodwork.components.inputs.keyword_voice import keyword_voice

            config["task_master"] = task_m
            return init_object(keyword_voice, **config)

        if type == "push_to_talk":
            from woodwork.components.inputs.push_to_talk import push_to_talk

            config["task_master"] = task_m
            return init_object(push_to_talk, **config)

        if type == "command_line":
            from woodwork.components.inputs.command_line import command_line

            config["task_master"] = task_m
            return init_object(command_line, **config)

    if component == "api":
        if type == "web":
            from woodwork.components.apis.web import web

            return init_object(web, **config)
        if type == "functions":
            from woodwork.components.apis.functions import functions

            return init_object(functions, **config)

    if component == "decomposer":
        config["output"] = task_m
        if type == "llm":
            from woodwork.components.decomposers.llm import llm

            return init_object(llm, **config)

    if component == "core":
        if type == "command_line":
            from woodwork.components.core.command_line import command_line

            return init_object(command_line, **config)

    if component == "output":
        if type == "voice":
            from woodwork.components.outputs.voice import voice

            return init_object(voice, **config)


def command_checker(commands):
    terminals_remaining = 1

    for _, command in commands.items():
        if command["component"] == "input" and command["type"] == "command_line":
            if terminals_remaining == 1:
                terminals_remaining = 0
            else:
                print("[ERROR] only one command line input can be initialised.")
                exit()


def get_declarations(file: str) -> list[str]:
    """Given a file, returns an array of strings containing the component declarations."""

    entry_pattern = r".+=.+\{"
    matches = []

    for match in re.finditer(entry_pattern, file):
        start_pos = match.start()
        stack = 1
        end_pos = match.end()

        # Use a stack to find the closing brace
        for i in range(end_pos, len(file)):
            char = file[i]
            if char == "{":
                stack += 1
            elif char == "}":
                stack -= 1
                if stack == 0:
                    end_pos = i + 1
                    break

        # Determine the starting line number
        line_number = file[:start_pos].count("\n") + 1

        # Add the full declaration text to the matches
        matches.append((file[start_pos:end_pos], line_number))

    return matches


def extract_nested_dict(key: str, text: str) -> str:
    # Match {key} followed by optional whitespace and a colon
    pattern = re.escape(key) + r"\s*:\s*\{"
    match = re.search(pattern, text)
    if not match:
        return ""

    # Start parsing from where the dictionary begins
    start_pos = match.end()  # Position after the colon and whitespace
    stack = []
    dict_start = -1

    for i in range(start_pos - 1, len(text)):
        char = text[i]
        if char == "{":
            if not stack:
                dict_start = i
            stack.append("{")
        elif char == "}":
            stack.pop()
            if not stack:  # Found the matching closing brace
                return text[dict_start : i + 1].strip()

    return ""  # Return empty string if no complete dictionary is found


def parse_config(entry: str) -> tuple[dict[Any, Any], list[Any] | Any]:
    config_items = list(
        map(
            lambda x: x.replace("\n", "").strip(),
            re.findall(r"\n[^\n]+", entry),
        ),
    )
    config_items = [x for x in config_items if x != ""]

    # If the value is a {, delete the nested elements (will be parsed later)
    i = 0
    brace_counter = 0
    deletion_mode = False
    while i < len(config_items):
        if "}" in config_items[i]:
            config_items.pop(i)
            brace_counter -= 1
            if brace_counter == 0:
                deletion_mode = False
        elif deletion_mode:
            if "{" in config_items[i]:
                brace_counter += 1
            config_items.pop(i)
        elif "{" in config_items[i]:
            brace_counter += 1
            deletion_mode = True
            i += 1
        else:
            i += 1

    config = {}
    # Make to a set
    depends_on = []
    for item in config_items:
        key = item.split(":", 1)[0].strip()
        value = item.split(":", 1)[1].strip()

        # Dealing with nested dictionaries:
        if value[0] == "{":
            # Find inside the string
            value, nested_deps = parse_config(extract_nested_dict(key, entry))
            depends_on += nested_deps

        # If the value starts with $, then it is a secret key in the .env file
        # Replace this with the secret
        elif value[0] == "$":
            value = os.getenv(value[1::])

        # If the value is an array, parse it as an array of references
        elif value[0] == "[":
            value = list(map(lambda x: x.strip(), value[1:-1:].split(",")))

            for i in range(len(value)):
                depends_on.append(value[i])

        elif (value[0] == '"' and value[-1] == '"') or (value[0] == "'" and value[-1] == "'"):
            value = value[1:-1:]

        # If the value is not a string, it references a variable
        # We replace this variable with a reference to the object
        # Could be a boolean
        elif value.lower() == "true":
            value = True
        elif value.lower() == "false":
            value = False

        else:
            # Add variable to depends_on
            depends_on.append(value)

        config[key] = value

    return config, depends_on


def parse(config: str, registry=None) -> dict:
    commands = {}
    if registry is None:
        registry = get_registry()

    # Load environment variables to be substituted in later
    current_directory = os.getcwd()
    load_dotenv(dotenv_path=os.path.join(current_directory, ".env"))

    # Get a list of all the component declarations
    entries = get_declarations(config)
    log.debug(entries)

    for entry, line_number in entries:
        command = {}
        # Replace these with some fancy regex
        command["variable"] = entry.split("=")[0].strip()
        command["component"] = entry.split("=")[1].split(" ")[1].strip()
        command["type"] = entry.split("=")[1].split(command["component"])[1].split("{")[0].strip()

        if command["variable"].lower() == "true" or command["variable"].lower() == "false":
            raise ForbiddenVariableNameError(
                "A boolean cannot be used as a variable name.",
                line_number,
                1,
                entry.split("\n", 1)[0],
            )

        if command["variable"] in commands:
            raise ForbiddenVariableNameError(
                "The same variable name cannot be used.",
                line_number,
                1,
                entry.split("\n", 1)[0],
            )

        # Parse config
        command["config"], command["depends_on"] = parse_config(entry)

        log.debug("[COMMAND] %s", command)
        commands[command["variable"]] = command

    command_checker(commands)

    tools = []
    for name in commands:
        dependency_resolver(commands, commands[name])
        tools.append(commands[name]["object"])
        registry.register(name, commands[name]["object"])

    task_m.add_tools(tools)

    return commands


def main_function(registry=None):
    current_directory = os.getcwd()
    with open(current_directory + "/main.ww") as f:
        lines = f.read()
        parse(lines, registry)


def embed_all():
    from woodwork.components.knowledge_bases.knowledge_base import knowledge_base

    for tool in task_m._tools:
        if isinstance(tool, knowledge_base):
            tool.embed_init()


def clear_all():
    from woodwork.components.knowledge_bases.knowledge_base import knowledge_base

    for tool in task_m._tools:
        if isinstance(tool, knowledge_base):
            tool.clear_all()


def validate_action_plan(workflow: dict[str, Any], tools: list):
    # Check tools exist
    for action in workflow["plan"]:
        tool_names = list(map(lambda x: x.name, tools))

        if action["tool"] not in tool_names:
            raise SyntaxError("Tool not found.")


def add_action_plan(file_path: str):
    from woodwork.components.decomposers.decomposer import decomposer

    for tool in task_m._tools:
        if isinstance(tool, decomposer):
            with open(file_path) as f:
                plan = json.loads(f.read())
                validate_action_plan(plan, task_m._tools)
                id = tool._cache_actions(plan)
                print(f"Successfully added a new workflow with ID: {id}")


def delete_action_plan(id: str):
    from woodwork.components.decomposers.decomposer import decomposer

    for tool in task_m._tools:
        if isinstance(tool, decomposer):
            tool._cache.run(f"""MATCH (n)-[:NEXT*]->(m)
                WHERE elementId(n) = "{id}"
                DETACH DELETE n
                DETACH DELETE m""")

    print(f"Successfully removed a new workflow with ID: {id}")


def find_action_plan(query: str):
    from woodwork.components.decomposers.decomposer import decomposer

    for tool in task_m._tools:
        if isinstance(tool, decomposer):
            similar_prompts = tool._cache.similarity_search(query, "Prompt", "value")
            num_results = min(len(similar_prompts), 10)

            print(f"Here are the top {num_results} most similar results:")
            for i in range(num_results):
                result = similar_prompts[i]

                print(f"{result['value']} {result['nodeID']}")
