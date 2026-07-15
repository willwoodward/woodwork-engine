"""Typed event name constants for the woodwork Python API.

String values map directly to what :class:`~woodwork.core.events.EventBus`
already uses internally, so these constants can be passed to
``component.hook()`` and ``component.pipe()`` without any translation.

Example::

    from woodwork import Event

    @assistant.hook(Event.Agent.TOOL_CALL)
    def on_tool_call(payload):
        print(payload)
"""


class _ComponentEvents:
    """Events shared by every component type."""

    STARTED = "component.started"
    STOPPED = "component.stopped"
    ERROR = "component.error"


class Event:
    """Namespace for typed event name constants."""

    class Agent(_ComponentEvents):
        TOOL_CALL = "tool.call"
        THOUGHT = "agent.thought"
        ACTION = "agent.action"
        STEP_COMPLETE = "agent.step_complete"

    class MCP(_ComponentEvents):
        pass

    class Input(_ComponentEvents):
        RECEIVED = "input.received"

    class LLM(_ComponentEvents):
        pass
