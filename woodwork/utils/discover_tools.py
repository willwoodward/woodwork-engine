"""
Utility to discover tool schemas from agents.

Tool-schema discovery now happens per-agent via the agent's EventBus and
WorkflowsFeature. This module is kept for backward compatibility.
"""

import logging
from typing import List

log = logging.getLogger(__name__)


def discover_and_register_tools(agent) -> List:
    """
    Discover tool schemas from *agent*.

    In the new architecture, schemas are surfaced per-agent by WorkflowsFeature.
    This function is a no-op shim kept for call-site compatibility.
    """
    tools = getattr(agent, "_tools", [])
    log.info("[ToolDiscovery] Agent '%s' has %d tools (no global bus registration)", agent.name, len(tools))
    return tools


def register_tool_schema_from_decorator(tool_class) -> None:
    """No-op shim — schema registration is now handled per-agent."""
    log.debug("[ToolDiscovery] register_tool_schema_from_decorator is a no-op in the new architecture")
