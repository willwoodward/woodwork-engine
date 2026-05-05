"""Backward-compatibility shim — re-exports from split modules.

The config_parser module has been split into:
- tokenizer.py: get_declarations, parse_component_declaration, parse_config, extract_nested_dict
- resolver.py: dependency_resolver, resolve_dict, command_checker
- factory.py: create_object, init_object, get_required_args, create_component_object, task_m
- parser.py: parse, main_function, parse_config_dict
- operations.py: embed_all, clear_all, delete_action_plan, find_action_plan
"""

# Re-export everything for backward compatibility
from woodwork.config.tokenizer import (  # noqa: F401
    get_declarations,
    extract_nested_dict,
    parse_component_declaration,
    parse_config,
)
from woodwork.config.resolver import (  # noqa: F401
    resolve_dict,
    dependency_resolver,
    command_checker,
)
from woodwork.config.factory import (  # noqa: F401
    task_m,
    _get_task_master,
    _TaskMasterProxy,
    get_required_args,
    init_object,
    create_object,
    create_component_object,
)
from woodwork.config.parser import (  # noqa: F401
    parse,
    main_function,
    _initialize_message_bus_integration,
    _async_initialize_message_bus,
    parse_config_dict,
)
from woodwork.config.operations import (  # noqa: F401
    embed_all,
    clear_all,
    delete_action_plan,
    find_action_plan,
)
