"""Main parse orchestrator for .ww configuration files."""

import logging
import os
from typing import Any, Dict

from dotenv import load_dotenv

from woodwork.config.tokenizer import get_declarations, parse_component_declaration, parse_config
from woodwork.config.resolver import dependency_resolver, command_checker
from woodwork.config.factory import build_components, create_component_object, create_object
from woodwork.utils.errors.errors import ForbiddenVariableNameError
from woodwork.deploy.registry import get_registry
from woodwork.components.component import Component
from woodwork.deploy.router import get_router, Deployment

log = logging.getLogger(__name__)


def parse(config: str, registry=None) -> dict:
    """Parse a .ww configuration string into resolved component commands."""
    commands: Dict[str, Any] = {}
    if registry is None:
        registry = get_registry()

    current_directory = os.getcwd()
    load_dotenv(dotenv_path=os.path.join(current_directory, ".env"))

    entries = get_declarations(config)
    log.debug(entries)

    for entry, line_number in entries:
        command: Dict[str, Any] = {}
        command["variable"], command["component"], command["type"] = parse_component_declaration(entry)

        if command["variable"].lower() in ("true", "false"):
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

        command["config"], command["depends_on"] = parse_config(entry)
        log.debug("[COMMAND] %s", command)
        commands[command["variable"]] = command

    command_checker(commands)

    router = get_router()
    for name in commands:
        dependency_resolver(commands, commands[name])
        obj = commands[name].get("object")
        if isinstance(obj, Component):
            registry.register(name, obj)
        if isinstance(obj, Deployment):
            for comp in obj.components:
                router.add(comp, obj)

    # Add local deployments
    for name, command in commands.items():
        obj = command.get("object")
        if isinstance(obj, Component) and obj.name not in router.components:
            router.add(obj)

    return commands


def main_function(registry=None) -> None:
    """Parse main.ww and start the new AsyncRuntime."""
    current_directory = os.getcwd()
    with open(os.path.join(current_directory, "main.ww")) as f:
        lines = f.read()

    commands = parse(lines, registry)
    components, dep_map = build_components(commands)

    from woodwork.core.runtime import AsyncRuntime
    import asyncio

    async def _run():
        runtime = AsyncRuntime()
        await runtime.start(components, dep_map)

    asyncio.run(_run())


def parse_config_dict(config_dict: dict) -> dict:
    """Parse a configuration dictionary (for programmatic / test use)."""
    log.debug("[ConfigParser] Parsing config dict with %d entries", len(config_dict))

    components = []
    component_configs: Dict[str, Any] = {}

    for component_name, component_config in config_dict.items():
        try:
            component_type = component_config.get("component", "unknown")
            type_name = component_config.get("type", "unknown")

            config_copy = component_config.copy()
            config_copy["name"] = component_name

            obj = create_component_object(component_type, type_name, config_copy)
            if obj:
                components.append(obj)
                component_configs[component_name] = {
                    "object": obj,
                    "component": component_type,
                    "variable": component_name,
                    "config": config_copy,
                }
            else:
                log.warning("[ConfigParser] Failed to create component: %s", component_name)

        except Exception as exc:
            log.error("[ConfigParser] Error creating component %s: %s", component_name, exc)

    log.info("[ConfigParser] Parsed %d components from dict", len(components))
    return {"components": components, "component_configs": component_configs}
