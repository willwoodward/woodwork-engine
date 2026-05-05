"""Main parse orchestrator for .ww configuration files.

Coordinates tokenizing, dependency resolution, and component creation.
"""

import logging
import os

from dotenv import load_dotenv

from woodwork.config.tokenizer import get_declarations, parse_component_declaration, parse_config
from woodwork.config.resolver import dependency_resolver, command_checker
from woodwork.config.factory import _get_task_master, create_component_object
from woodwork.utils.errors.errors import ForbiddenVariableNameError
from woodwork.deploy.registry import get_registry
from woodwork.components.component import Component
from woodwork.deploy.router import get_router, Deployment

log = logging.getLogger(__name__)


def parse(config: str, registry=None) -> dict:
    """Parse a .ww configuration string into resolved component commands."""
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
        command["variable"], command["component"], command["type"] = parse_component_declaration(entry)

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

    tools: list[Component] = []
    router = get_router()
    for name in commands:
        dependency_resolver(commands, commands[name])
        obj = commands[name]["object"]
        if isinstance(obj, Component):
            tools.append(commands[name]["object"])
            registry.register(name, commands[name]["object"])
        if isinstance(obj, Deployment):
            for comp in obj.components:
                router.add(comp, obj)

    # Add local deployments
    for comp in tools:
        if comp.name not in router.components:
            router.add(comp)

    # Set the flag to activate message bus mode
    import woodwork.globals as globals

    globals.global_config["message_bus_active"] = True
    log.info("[ConfigParser] Message bus mode activated - initialization deferred to DistributedStartupCoordinator")

    _get_task_master().add_tools(tools)

    return commands


def _initialize_message_bus_integration(commands: dict) -> None:
    """Synchronously initialize message bus integration with component configurations."""
    try:
        from woodwork.runtime.message_bus.integration import (
            initialize_global_message_bus_integration_sync,
            get_global_message_bus_manager,
        )
        from woodwork.runtime.message_bus.factory import configure_global_message_bus

        log.info("[ConfigParser] Initializing message bus integration...")

        # Extract component instances for routing
        component_configs = {}
        deployment_config = None

        for name, command_data in commands.items():
            obj = command_data.get("object")
            if hasattr(obj, "component") and hasattr(obj, "config"):
                component_configs[name] = {
                    "object": obj,
                    **obj.config,
                    "component": obj.component,
                    "type": obj.type,
                    "name": name,
                }
            elif isinstance(obj, Deployment):
                if name == "deployment" or obj.component == "deployment":
                    deployment_config = command_data.get("config", {})

        log.debug("[ConfigParser] Found %d components for message bus routing", len(component_configs))

        # Activate message bus globally
        import woodwork.globals as globals

        globals.global_config["message_bus_active"] = True
        log.info("[ConfigParser] Message bus mode activated - Task Master will be disabled")

        # Configure custom message bus if specified
        if deployment_config and "message_bus" in deployment_config:
            message_bus_config = deployment_config["message_bus"]
            log.info("[ConfigParser] Found custom message bus configuration: %s", message_bus_config)
            if isinstance(message_bus_config, str):
                if message_bus_config.startswith("redis://"):
                    message_bus_config = {"type": "redis", "redis_url": message_bus_config}
                elif message_bus_config.startswith("nats://"):
                    message_bus_config = {"type": "nats", "nats_url": message_bus_config}
                else:
                    log.warning("[ConfigParser] Unknown message bus URL format: %s", message_bus_config)
                    message_bus_config = {"type": "auto"}
            configure_global_message_bus(message_bus_config)
            log.info("[ConfigParser] Configured custom message bus")
        else:
            log.info("[ConfigParser] Using default message bus configuration")

        # Initialize message bus integration synchronously
        initialize_global_message_bus_integration_sync(component_configs)
        log.info("[ConfigParser] Message bus integration initialized with %d components", len(component_configs))

        # Ensure all components have the required integration attributes
        for cfg in component_configs.values():
            comp = cfg.get("object")
            if comp:
                if not hasattr(comp, "_integration_ready"):
                    comp._integration_ready = True

                if not hasattr(comp, "_router") or comp._router is None:
                    try:
                        log.debug("[ConfigParser] Setting unified event bus router on component '%s'", comp.name)
                        comp._router_pending = True
                    except Exception as e:
                        log.warning("[ConfigParser] Failed to prepare router for component '%s': %s", comp.name, e)

        # Log status
        manager = get_global_message_bus_manager()
        stats = manager.get_manager_stats()
        log.info(
            "[ConfigParser] Message bus status: %s",
            {
                "integration_active": stats["integration_active"],
                "registered_components": stats["registered_components"],
                "message_bus_healthy": stats["message_bus_healthy"],
            },
        )
        if stats.get("router_stats", {}).get("routing_table"):
            log.debug("[ConfigParser] Routing table: %s", stats["router_stats"]["routing_table"])

    except Exception as e:
        log.error("[ConfigParser] Failed to initialize message bus integration: %s", e)
        log.error("[ConfigParser] Components will work without distributed messaging")


async def _async_initialize_message_bus(component_configs: dict) -> None:
    """Async helper for message bus initialization."""
    try:
        from woodwork.runtime.message_bus.integration import initialize_global_message_bus_integration

        await initialize_global_message_bus_integration(component_configs)
        log.info("[ConfigParser] Message bus integration initialized with %d components", len(component_configs))

        from woodwork.runtime.message_bus.integration import get_global_message_bus_manager

        manager = get_global_message_bus_manager()
        stats = manager.get_manager_stats()

        log.info(
            "[ConfigParser] Message bus status: %s",
            {
                "integration_active": stats["integration_active"],
                "registered_components": stats["registered_components"],
                "message_bus_healthy": stats["message_bus_healthy"],
            },
        )

        if stats.get("router_stats", {}).get("routing_table"):
            log.debug("[ConfigParser] Routing table: %s", stats["router_stats"]["routing_table"])

    except Exception as e:
        log.error("[ConfigParser] Error in async message bus initialization: %s", e)


def main_function(registry=None):
    """Parse configuration file and initialize components.

    Note: Message bus initialization is now handled by DistributedStartupCoordinator
    to ensure proper event loop ownership and clean startup sequence.
    """
    current_directory = os.getcwd()
    with open(current_directory + "/main.ww") as f:
        lines = f.read()
        parse(lines, registry)


def parse_config_dict(config_dict: dict) -> dict:
    """Parse configuration dictionary for unified async runtime.

    Creates components from a dictionary configuration,
    similar to parsing .ww files but for programmatic use.
    """
    log.debug("[ConfigParser] Parsing config dictionary with %d entries", len(config_dict))

    components = []
    component_configs = {}

    for component_name, component_config in config_dict.items():
        try:
            component_type = component_config.get("component", "unknown")
            type_name = component_config.get("type", "unknown")

            log.debug("[ConfigParser] Creating component: %s (%s/%s)", component_name, component_type, type_name)

            config_copy = component_config.copy()
            config_copy["name"] = component_name

            component_obj = create_component_object(component_type, type_name, config_copy)

            if component_obj:
                components.append(component_obj)
                component_configs[component_name] = {
                    "object": component_obj,
                    "component": component_type,
                    "variable": component_name,
                    "config": config_copy,
                }
                log.debug("[ConfigParser] Created component: %s", component_name)
            else:
                log.warning("[ConfigParser] Failed to create component: %s", component_name)

        except Exception as e:
            log.error("[ConfigParser] Error creating component %s: %s", component_name, e)

    log.info("[ConfigParser] Parsed %d components from dictionary", len(components))

    return {"components": components, "component_configs": component_configs}
