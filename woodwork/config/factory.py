"""Component factory for creating component instances from parsed declarations."""

import inspect
import logging
from typing import Any, Dict, List, Tuple

from woodwork.utils.errors.errors import MissingConfigKeyError

log = logging.getLogger(__name__)


def get_required_args(cls) -> List[str]:
    """Return required (no-default) constructor params for *cls*, excluding 'component'/'Deployment'."""
    required_args = []
    for base in inspect.getmro(cls):
        if base.__name__ in ("Component", "Deployment"):
            continue
        constructor = inspect.signature(base.__init__)
        for name, param in constructor.parameters.items():
            if (
                param.default is inspect.Parameter.empty
                and param.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
                and name != "self"
            ):
                required_args.append(name)
    return list(set(required_args))


def init_object(cls, **params) -> Any:
    """Instantiate *cls* with *params*, raising on missing required args."""
    required_args = get_required_args(cls)
    missing = [a for a in required_args if a not in params]

    if len(missing) == 1:
        raise MissingConfigKeyError(f'Key "{missing[0]}" missing from {cls.__name__}.')
    if len(missing) > 1:
        raise MissingConfigKeyError(f"Keys {missing} missing from {cls.__name__}.")

    return cls(**params)


def create_object(command: Dict[str, Any]) -> Any:
    """Create a component object from a parsed command dictionary."""
    component = command["component"]
    type_ = command["type"]
    variable = command["variable"]
    config = command["config"].copy()

    log.debug("[create_object] Creating %s with keys: %s", variable, list(command.keys()))

    config["name"] = variable
    config["component"] = component
    config["type"] = type_

    for key in ("hooks", "pipes"):
        if key in command:
            config[key] = command[key]

    if component == "knowledge_base":
        if type_ == "chroma":
            from woodwork.components.knowledge_bases.vector_databases.chroma import ChromaDB
            return init_object(ChromaDB, **config)
        if type_ == "neo4j":
            from woodwork.components.knowledge_bases.graph_databases.neo4j import Neo4j
            return init_object(Neo4j, **config)
        if type_ == "text_file":
            from woodwork.components.knowledge_bases.text_files.text_file import TextFile
            return init_object(TextFile, **config)

    if component == "memory":
        if type_ == "short_term":
            from woodwork.components.memory.short_term import ShortTermMemory
            return init_object(ShortTermMemory, **config)

    if component == "llm":
        if type_ == "hugging_face":
            from woodwork.components.llms.hugging_face import HuggingFaceLLM
            return init_object(HuggingFaceLLM, **config)
        if type_ == "openai":
            from woodwork.components.llms.openai import OpenAILLM
            return init_object(OpenAILLM, **config)
        if type_ == "claude":
            from woodwork.components.llms.claude import ClaudeLLM
            return init_object(ClaudeLLM, **config)
        if type_ == "ollama":
            from woodwork.components.llms.ollama import OllamaLLM
            return init_object(OllamaLLM, **config)

    if component == "input":
        if type_ == "keyword_voice":
            from woodwork.components.inputs.keyword_voice import KeywordVoice
            return init_object(KeywordVoice, **config)
        if type_ == "push_to_talk":
            from woodwork.components.inputs.push_to_talk import PushToTalk
            return init_object(PushToTalk, **config)
        if type_ == "command_line":
            from woodwork.components.inputs.command_line import CommandLineInput
            return init_object(CommandLineInput, **config)
        if type_ == "api":
            from woodwork.components.inputs.api_input import APIInput
            return init_object(APIInput, **config)

    if component == "api":
        if type_ == "web":
            from woodwork.components.apis.web import Web
            return init_object(Web, **config)
        if type_ == "functions":
            from woodwork.components.apis.functions import Functions
            return init_object(Functions, **config)

    if component == "agent":
        if type_ == "llm":
            from woodwork.components.agents.llm import LLMAgent
            return init_object(LLMAgent, **config)

    if component == "core":
        if type_ == "command_line":
            from woodwork.components.tools.command_line import CommandLineTool
            return init_object(CommandLineTool, **config)
        if type_ == "code":
            from woodwork.components.tools.code import CodeTool
            return init_object(CodeTool, **config)

    if component == "output":
        if type_ == "voice":
            from woodwork.components.outputs.voice import Voice
            return init_object(Voice, **config)

    if component == "mcp":
        if type_ == "server":
            from woodwork.components.mcp import MCPServer
            return init_object(MCPServer, **config)

    if component == "environment":
        if type_ == "coding":
            from woodwork.components.environments.coding import Coding
            return init_object(Coding, **config)

    if component == "vm":
        if type_ == "server":
            from woodwork.deploy.router import ServerDeployment
            return init_object(ServerDeployment, **config)

    log.warning("[factory] Unknown component: %s / %s", component, type_)
    return None


def build_components(declarations: Dict[str, Dict[str, Any]]) -> Tuple[List[Any], Dict[str, List[str]]]:
    """
    Build component instances from resolved declarations.

    Returns:
        (components, dep_map) where dep_map maps name → list[dependency names].
    """
    from woodwork.components.component import Component
    from woodwork.deploy.deployment import Deployment

    components: List[Any] = []
    dep_map: Dict[str, List[str]] = {}

    for name, command in declarations.items():
        obj = command.get("object")
        if obj is None:
            continue
        if isinstance(obj, Component):
            components.append(obj)
            dep_map[name] = command.get("depends_on", [])
        elif isinstance(obj, Deployment):
            for comp in obj.components:
                components.append(comp)
                dep_map[comp.name] = []

    return components, dep_map


def create_component_object(component_type: str, type_name: str, config: dict) -> Any:
    """Create a component from type information (for programmatic/dict-based config)."""
    try:
        if component_type in ("input", "inputs"):
            if type_name == "api":
                from woodwork.components.inputs.api_input import APIInput
                return init_object(APIInput, **config)
            elif type_name == "command_line":
                from woodwork.components.inputs.command_line import CommandLineInput
                return init_object(CommandLineInput, **config)

        elif component_type in ("llm", "llms"):
            if type_name == "openai":
                from woodwork.components.llms.openai import OpenAILLM
                return init_object(OpenAILLM, **config)
            elif type_name == "ollama":
                from woodwork.components.llms.ollama import OllamaLLM
                return init_object(OllamaLLM, **config)

        elif component_type in ("agent", "agents"):
            if type_name == "llm":
                from woodwork.components.agents.llm import LLMAgent
                return init_object(LLMAgent, **config)

        elif component_type in ("output", "outputs"):
            if type_name == "console":
                from woodwork.components.outputs.console import Console
                return init_object(Console, **config)

        log.warning("[factory] Unknown component type: %s/%s", component_type, type_name)
        return None

    except Exception as exc:
        log.error("[factory] Error creating %s/%s: %s", component_type, type_name, exc)
        return None
