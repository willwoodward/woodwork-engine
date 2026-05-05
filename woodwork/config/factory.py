"""Component factory for creating component instances from parsed declarations.

Handles lazy task master initialization and the component creation dispatch.
"""

import inspect
import logging

from woodwork.runtime.task_master import task_master
from woodwork.utils.errors.errors import MissingConfigKeyError

log = logging.getLogger(__name__)

# Lazy-initialize task_master to avoid registration during module import
_task_m = None


def _get_task_master():
    """Lazy initialization of task_master."""
    global _task_m
    if _task_m is None:
        _task_m = task_master(name="task_master")
    return _task_m


class _TaskMasterProxy:
    """Proxy object that lazily initializes task_master on first access."""

    def __getattr__(self, name):
        return getattr(_get_task_master(), name)


task_m = _TaskMasterProxy()


def get_required_args(cls):
    """Get required constructor arguments for a class and its parents, excluding 'component' and 'Deployment'."""
    required_args = []

    for base in inspect.getmro(cls):
        if base.__name__ == "component":
            continue
        if base.__name__ == "Deployment":
            continue
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
    """Initialize a component object, checking for required arguments."""
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
    """Create a component object from a parsed command dictionary."""
    component = command["component"]
    type = command["type"]
    variable = command["variable"]
    config = command["config"].copy()

    log.debug(f"[create_object] Creating {variable} with keys: {list(command.keys())}")
    if "hooks" in command:
        log.debug(f"[create_object] Found hooks: {command['hooks']}")
    if "pipes" in command:
        log.debug(f"[create_object] Found pipes: {command['pipes']}")

    # Add metadata to the config (required by new component base class)
    config["name"] = variable
    config["component"] = component
    config["type"] = type

    # Include hooks and pipes in config if they exist
    if "hooks" in command:
        config["hooks"] = command["hooks"]
        log.debug(f"[create_object] Added hooks to config for {variable}")
    if "pipes" in command:
        config["pipes"] = command["pipes"]
        log.debug(f"[create_object] Added pipes to config for {variable}")

    if component == "knowledge_base":
        if type == "chroma":
            from woodwork.components.knowledge_bases.vector_databases.chroma import chroma

            return init_object(chroma, **config)
        if type == "neo4j":
            from woodwork.components.knowledge_bases.graph_databases.neo4j import neo4j

            return init_object(neo4j, **config)
        if type == "text_file":
            from woodwork.components.knowledge_bases.text_files.text_file import text_file

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
        if type == "claude":
            from woodwork.components.llms.claude import claude

            return init_object(claude, **config)
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

        if type == "api":
            from woodwork.components.inputs.api_input import api_input

            return init_object(api_input, **config)

    if component == "api":
        if type == "web":
            from woodwork.components.apis.web import web

            return init_object(web, **config)
        if type == "functions":
            from woodwork.components.apis.functions import functions

            return init_object(functions, **config)

    if component == "agent":
        config["task_m"] = task_m
        if type == "llm":
            from woodwork.components.agents.llm import llm

            return init_object(llm, **config)

    if component == "core":
        if type == "command_line":
            from woodwork.components.tools.command_line import command_line

            return init_object(command_line, **config)
        if type == "code":
            from woodwork.components.tools.code import code

            return init_object(code, **config)

    if component == "output":
        if type == "voice":
            from woodwork.components.outputs.voice import voice

            return init_object(voice, **config)

    if component == "mcp":
        if type == "server":
            from woodwork.components.mcp import MCPServer

            return init_object(MCPServer, **config)

    if component == "environment":
        if type == "coding":
            from woodwork.components.environments.coding import coding

            return init_object(coding, **config)

    # Deployment components
    if component == "vm":
        if type == "server":
            from woodwork.deploy.router import ServerDeployment

            return init_object(ServerDeployment, **config)


def create_component_object(component_type: str, type_name: str, config: dict):
    """Create component object from type information (for programmatic/dict-based config)."""
    try:
        if component_type == "input" or component_type == "inputs":
            if type_name == "api":
                from woodwork.components.inputs.api_input import api_input

                return init_object(api_input, **config)
            elif type_name == "command_line":
                from woodwork.components.inputs.command_line import command_line

                config["task_master"] = task_m
                return init_object(command_line, **config)

        elif component_type == "llm" or component_type == "llms":
            if type_name == "openai":
                from woodwork.components.llms.openai import openai

                return init_object(openai, **config)
            elif type_name == "ollama":
                from woodwork.components.llms.ollama import ollama

                return init_object(ollama, **config)

        elif component_type == "agent" or component_type == "agents":
            if type_name == "llm":
                from woodwork.components.agents.llm import llm

                config["task_m"] = task_m
                return init_object(llm, **config)

        elif component_type == "output" or component_type == "outputs":
            if type_name == "console":
                from woodwork.components.outputs.console import console

                return init_object(console, **config)

        log.warning("[ConfigParser] Unknown component type: %s/%s", component_type, type_name)
        return None

    except Exception as e:
        log.error("[ConfigParser] Error creating %s/%s: %s", component_type, type_name, e)
        return None
