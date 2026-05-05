"""
Utility to discover and register tool schemas from agents.

This module provides helpers to automatically discover tool schemas
from agents and register them with the unified event bus.
"""

import logging
from typing import List
from woodwork.runtime.unified_event_bus import get_global_event_bus
from woodwork.types.tool_schema import ToolSchema

log = logging.getLogger(__name__)


def discover_and_register_tools(agent) -> List[ToolSchema]:
    """
    Discover tools from agent and register schemas with event bus.

    This should be called after agent initialization to make tools
    available to the workflow builder.

    Args:
        agent: Agent component with _tools attribute

    Returns:
        List of discovered and registered tool schemas

    Example:
        ```python
        from woodwork.utils.discover_tools import discover_and_register_tools

        # After agent is created
        agent = openai_agent(...)

        # Discover and register tool schemas
        schemas = discover_and_register_tools(agent)
        print(f"Discovered {len(schemas)} tools")
        ```
    """
    event_bus = get_global_event_bus()
    schemas = event_bus.discover_tools_from_agent(agent)

    log.info(f"[ToolDiscovery] Registered {len(schemas)} tool schemas from agent '{agent.name}'")

    return schemas


def register_tool_schema_from_decorator(tool_class) -> None:
    """
    Register tool schema from decorator metadata.

    Args:
        tool_class: Tool class with @tool_schema decorator

    Example:
        ```python
        from woodwork.decorators import tool_schema
        from woodwork.utils.discover_tools import register_tool_schema_from_decorator

        @tool_schema(...)
        class my_custom_tool:
            pass

        # Manually register if not discovered from agent
        register_tool_schema_from_decorator(my_custom_tool)
        ```
    """
    event_bus = get_global_event_bus()

    if hasattr(tool_class, "__tool_schema__"):
        schema = tool_class.__tool_schema__
        event_bus.register_tool_schema(schema)
        log.info(f"[ToolDiscovery] Registered schema for {schema.tool_name}")
    else:
        log.warning(f"[ToolDiscovery] Tool class {tool_class.__name__} has no __tool_schema__")
