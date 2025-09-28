import inspect
import logging
import os
import re

from dotenv import load_dotenv
from typing import Any

from woodwork.core.task_master import task_master
from woodwork.utils.errors.errors import (
    ForbiddenVariableNameError,
    MissingConfigKeyError,
)
from woodwork.deployments.registry import get_registry
from woodwork.components.component import component
from woodwork.deployments.router import get_router, Deployment

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
        # Skip empty dependencies
        if not dependency or dependency.strip() == "":
            continue
            
        # Check if dependency exists
        if dependency not in commands:
            raise ValueError(f"Dependency '{dependency}' not found for component '{component.get('variable', 'unknown')}'")
            
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

    # Debug: show what's in the parsed command
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

            # API input doesn't need task_master - it uses messaging system
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
            from woodwork.components.core.command_line import command_line

            return init_object(command_line, **config)
        if type == "code":
            from woodwork.components.core.code import code

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
            from woodwork.deployments.router import ServerDeployment

            return init_object(ServerDeployment, **config)


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

    # Handle multiline arrays by joining them
    merged_items = []
    i = 0
    while i < len(config_items):
        item = config_items[i]
        
        # Check if this line starts an array
        if ":" in item and "[" in item and "]" not in item:
            # This is a multiline array - collect all lines until we find the closing ]
            array_lines = [item]
            i += 1
            while i < len(config_items) and "]" not in config_items[i]:
                array_lines.append(config_items[i])
                i += 1
            # Add the closing line
            if i < len(config_items):
                array_lines.append(config_items[i])
            
            # Join all array lines into one
            key_part = array_lines[0].split(":", 1)[0] + ":"
            array_content = " ".join([line.split(":", 1)[1] if ":" in line else line for line in array_lines])
            merged_items.append(key_part + " " + array_content.strip())
        else:
            merged_items.append(item)
        i += 1
    
    config_items = merged_items

    # If the value is a {, delete the nested elements (will be parsed later)
    # BUT preserve dictionary content that's inside arrays (for hooks/pipes)
    i = 0
    brace_counter = 0
    deletion_mode = False
    while i < len(config_items):
        if "}" in config_items[i]:
            # Check if this closing brace is part of an array
            line = config_items[i]
            # If the line contains both ] and }, it's likely ending an array with dict content
            if "]" in line and "}" in line:
                # Keep this line, it's array content
                i += 1
                brace_counter -= 1
                if brace_counter == 0:
                    deletion_mode = False
            else:
                config_items.pop(i)
                brace_counter -= 1
                if brace_counter == 0:
                    deletion_mode = False
        elif deletion_mode:
            # Check if this line is part of an array structure
            line = config_items[i]
            # If it contains array-like content or is indented (suggesting it's array content), keep it
            if ("[" in line or "]" in line or 
                line.startswith("    ") or line.startswith("\t") or
                any(key in line for key in ["event:", "script_path:", "function_name:"])):
                # This looks like array content, keep it
                i += 1
            else:
                if "{" in config_items[i]:
                    brace_counter += 1
                config_items.pop(i)
        elif "{" in config_items[i]:
            # Check if this { is part of an array
            line = config_items[i]
            if "[" in line:  # This looks like an array with dict content
                # Don't enter deletion mode, just continue
                i += 1
            else:
                brace_counter += 1
                deletion_mode = True
                i += 1
        else:
            i += 1

    config = {}
    # Make to a set
    depends_on = []
    for item in config_items:
        # Skip empty lines or lines without colons
        if not item.strip() or ":" not in item:
            continue
            
        parts = item.split(":", 1)
        if len(parts) < 2:
            continue
            
        key = parts[0].strip()
        value = parts[1].strip()

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
            array_content = value[1:-1]  # Remove [ and ]
            array_items = []
            
            # Parse array items that can be strings, dictionaries, or simple references
            current_item = ""
            in_quotes = False
            quote_char = None
            brace_count = 0
            
            i = 0
            while i < len(array_content):
                char = array_content[i]
                
                if not in_quotes and char in ['"', "'"]:
                    in_quotes = True
                    quote_char = char
                    current_item += char
                elif in_quotes and char == quote_char:
                    in_quotes = False
                    current_item += char
                    quote_char = None
                elif not in_quotes and char == '{':
                    brace_count += 1
                    current_item += char
                elif not in_quotes and char == '}':
                    brace_count -= 1
                    current_item += char
                elif not in_quotes and char == ',' and brace_count == 0:
                    # End of current item
                    cleaned_item = current_item.strip()
                    if cleaned_item:
                        # Check if it's a dictionary-like structure
                        if cleaned_item.startswith('{') and cleaned_item.endswith('}'):
                            # Parse as dictionary
                            dict_content = cleaned_item[1:-1].strip()  # Remove { and }
                            parsed_dict = {}
                            
                            # Split by lines and parse key-value pairs
                            dict_lines = [line.strip() for line in dict_content.split('\n') if line.strip()]
                            for line in dict_lines:
                                if ':' in line:
                                    line_key, line_value = line.split(':', 1)
                                    line_key = line_key.strip().strip('"\'')
                                    line_value = line_value.strip().strip('"\'')
                                    
                                    # Map common keys for hooks and pipes
                                    if line_key in ['event', 'script_path', 'function_name']:
                                        parsed_dict[line_key] = line_value
                                else:
                                    # Handle lines without colons (might be values from multiline parsing)
                                    # Try to extract quoted strings as values
                                    if '"' in line or "'" in line:
                                        parts = re.findall(r'["\']([^"\']*)["\']', line)
                                        if len(parts) == 3:  # event, script_path, function_name
                                            parsed_dict['event'] = parts[0]
                                            parsed_dict['script_path'] = parts[1] 
                                            parsed_dict['function_name'] = parts[2]
                            
                            array_items.append(parsed_dict)
                        else:
                            # Remove outer quotes if present
                            if ((cleaned_item.startswith('"') and cleaned_item.endswith('"')) or 
                                (cleaned_item.startswith("'") and cleaned_item.endswith("'"))):
                                cleaned_item = cleaned_item[1:-1]
                            array_items.append(cleaned_item)
                    current_item = ""
                else:
                    current_item += char
                i += 1
            
            # Don't forget the last item
            if current_item.strip():
                cleaned_item = current_item.strip()
                if cleaned_item.startswith('{') and cleaned_item.endswith('}'):
                    # Parse as dictionary
                    dict_content = cleaned_item[1:-1].strip()
                    parsed_dict = {}
                    
                    # Handle the case where we have space-separated quoted strings
                    if '"' in dict_content or "'" in dict_content:
                        parts = re.findall(r'["\']([^"\']*)["\']', dict_content)
                        if len(parts) == 3:  # event, script_path, function_name
                            parsed_dict['event'] = parts[0]
                            parsed_dict['script_path'] = parts[1]
                            parsed_dict['function_name'] = parts[2]
                    
                    array_items.append(parsed_dict)
                else:
                    if ((cleaned_item.startswith('"') and cleaned_item.endswith('"')) or 
                        (cleaned_item.startswith("'") and cleaned_item.endswith("'"))):
                        cleaned_item = cleaned_item[1:-1]
                    array_items.append(cleaned_item)
            
            value = array_items
            
            # Only add to dependencies if they look like simple variable references
            for item in value:
                # Only treat as dependency if it's a simple string identifier
                if (isinstance(item, str) and
                    re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', item) and
                    not item.startswith('$')):
                    depends_on.append(item)

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

    tools: list[component] = []
    router = get_router()
    for name in commands:
        dependency_resolver(commands, commands[name])
        obj = commands[name]["object"]
        if isinstance(obj, component):
            tools.append(commands[name]["object"])
            registry.register(name, commands[name]["object"])
        if isinstance(obj, Deployment):
            # Add each component to the router
            for comp in obj.components:
                router.add(comp, obj)

    # Add local deployments
    for comp in tools:
        if comp.name not in router.components:
            router.add(comp)

    # NOTE: Just set the flag to activate message bus mode
    # Full initialization will be handled by DistributedStartupCoordinator in proper event loop
    import woodwork.globals as globals
    globals.global_config["message_bus_active"] = True
    log.info("[ConfigParser] Message bus mode activated - initialization deferred to DistributedStartupCoordinator")
    
    task_m.add_tools(tools)

    return commands


def _initialize_message_bus_integration(commands: dict) -> None:
    """Synchronously initialize message bus integration with component configurations"""
    try:
        from woodwork.core.message_bus.integration import (
            initialize_global_message_bus_integration,
            initialize_global_message_bus_integration_sync,
            get_global_message_bus_manager
        )
        from woodwork.core.message_bus.factory import configure_global_message_bus

        log.info("[ConfigParser] Initializing message bus integration...")

        # Extract component instances for routing
        component_configs = {}
        deployment_config = None

        for name, command_data in commands.items():
            obj = command_data.get("object")
            if hasattr(obj, "component") and hasattr(obj, "config"):
                # Regular component
                component_configs[name] = {
                    "object": obj,  # store instance
                    **obj.config,
                    "component": obj.component,
                    "type": obj.type,
                    "name": name
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

        # Initialize message bus integration synchronously without separate event loop
        initialize_global_message_bus_integration_sync(component_configs)
        log.info("[ConfigParser] Message bus integration initialized with %d components", len(component_configs))

        # Ensure all components have the required integration attributes
        for cfg in component_configs.values():
            comp = cfg.get("object")
            if comp:
                if not hasattr(comp, "_integration_ready"):
                    comp._integration_ready = True
                # Let MessageBusIntegration handle _message_bus itself in _ensure_message_bus_integration
                # Don't set _message_bus to GlobalMessageBusManager - it should be the actual bus

                # Set unified event bus router if not already set
                if not hasattr(comp, "_router") or comp._router is None:
                    from woodwork.core.unified_event_bus import get_global_event_bus
                    try:
                        # This is sync context, so we need to handle async differently
                        log.debug("[ConfigParser] Setting unified event bus router on component '%s'", comp.name)
                        # For now, just set a placeholder - the actual router will be set in async context
                        comp._router_pending = True
                    except Exception as e:
                        log.warning("[ConfigParser] Failed to prepare router for component '%s': %s", comp.name, e)

        # Log status
        manager = get_global_message_bus_manager()
        stats = manager.get_manager_stats()
        log.info("[ConfigParser] Message bus status: %s", {
            "integration_active": stats["integration_active"],
            "registered_components": stats["registered_components"],
            "message_bus_healthy": stats["message_bus_healthy"]
        })
        if stats.get("router_stats", {}).get("routing_table"):
            log.debug("[ConfigParser] Routing table: %s", stats["router_stats"]["routing_table"])

    except Exception as e:
        log.error("[ConfigParser] Failed to initialize message bus integration: %s", e)
        log.error("[ConfigParser] Components will work without distributed messaging")



async def _async_initialize_message_bus(component_configs: dict) -> None:
    """Async helper for message bus initialization"""
    try:
        from woodwork.core.message_bus.integration import initialize_global_message_bus_integration
        
        await initialize_global_message_bus_integration(component_configs)
        log.info("[ConfigParser] Message bus integration initialized with %d components", len(component_configs))
        
        # Log routing configuration for debugging
        from woodwork.core.message_bus.integration import get_global_message_bus_manager
        manager = get_global_message_bus_manager()
        stats = manager.get_manager_stats()
        
        log.info("[ConfigParser] Message bus status: %s", {
            "integration_active": stats["integration_active"],
            "registered_components": stats["registered_components"],
            "message_bus_healthy": stats["message_bus_healthy"]
        })
        
        if stats.get("router_stats", {}).get("routing_table"):
            log.debug("[ConfigParser] Routing table: %s", stats["router_stats"]["routing_table"])
        
    except Exception as e:
        log.error("[ConfigParser] Error in async message bus initialization: %s", e)


def main_function(registry=None):
    """
    Parse configuration file and initialize components.

    Note: Message bus initialization is now handled by DistributedStartupCoordinator
    to ensure proper event loop ownership and clean startup sequence.
    """
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


def delete_action_plan(id: str):
    from woodwork.components.agents.agent import agent

    for tool in task_m._tools:
        if isinstance(tool, agent):
            tool._cache.run(f"""MATCH (n)-[:NEXT*]->(m)
                WHERE elementId(n) = "{id}"
                DETACH DELETE n
                DETACH DELETE m""")

    print(f"Successfully removed a new workflow with ID: {id}")


def find_action_plan(query: str):
    from woodwork.components.agents.agent import agent

    for tool in task_m._tools:
        if isinstance(tool, agent):
            similar_prompts = tool._cache.similarity_search(query, "Prompt", "value")
            num_results = min(len(similar_prompts), 10)

            print(f"Here are the top {num_results} most similar results:")
            for i in range(num_results):
                result = similar_prompts[i]

                print(f"{result['value']} {result['nodeID']}")


def parse_config_dict(config_dict: dict) -> dict:
    """
    Parse configuration dictionary for unified async runtime.

    This creates components from a dictionary configuration,
    similar to parsing .ww files but for programmatic use.
    """
    log.debug("[ConfigParser] Parsing config dictionary with %d entries", len(config_dict))

    components = []
    component_configs = {}

    # Convert dictionary entries to component objects
    for component_name, component_config in config_dict.items():
        try:
            # Extract component info
            component_type = component_config.get("component", "unknown")
            type_name = component_config.get("type", "unknown")

            log.debug("[ConfigParser] Creating component: %s (%s/%s)",
                     component_name, component_type, type_name)

            # Create component using existing factory functions
            config_copy = component_config.copy()
            config_copy["name"] = component_name

            component_obj = create_component_object(component_type, type_name, config_copy)

            if component_obj:
                components.append(component_obj)
                component_configs[component_name] = {
                    "object": component_obj,
                    "component": component_type,
                    "variable": component_name,
                    "config": config_copy
                }

                log.debug("[ConfigParser] Created component: %s", component_name)
            else:
                log.warning("[ConfigParser] Failed to create component: %s", component_name)

        except Exception as e:
            log.error("[ConfigParser] Error creating component %s: %s", component_name, e)

    log.info("[ConfigParser] Parsed %d components from dictionary", len(components))

    return {
        "components": components,
        "component_configs": component_configs
    }


def create_component_object(component_type: str, type_name: str, config: dict):
    """Create component object from type information."""
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

        # Add more component types as needed
        log.warning("[ConfigParser] Unknown component type: %s/%s", component_type, type_name)
        return None

    except Exception as e:
        log.error("[ConfigParser] Error creating %s/%s: %s", component_type, type_name, e)
        return None


def parse_config_file(file_path: str) -> dict:
    """Parse .ww configuration file."""
    # This is a wrapper around existing parse functionality
    # but returns format compatible with AsyncRuntime

    # Read and parse the file (use existing logic)
    with open(file_path, 'r') as f:
        content = f.read()

    # Use existing parsing logic but adapt output format
    # This is a simplified version - you may need to adapt based on your existing parse logic

    # For now, return a basic structure
    # You would adapt your existing parse logic here
    log.warning("[ConfigParser] File parsing not fully implemented - returning empty config")
    return {"components": [], "component_configs": {}}
