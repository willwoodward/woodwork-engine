"""Convenience re-export for Agent components.

Example::

    from woodwork.agents import Agent

    assistant = Agent(
        name="assistant",
        model=model,
        tools=[search],
        input=cli,
        prompt=File("system.txt"),
    )
"""

from typing import Any, List, Optional

from woodwork.components.agents.llm import LLMAgent


class Agent(LLMAgent):
    """Agent component for the woodwork Python API.

    A thin subclass of :class:`~woodwork.components.agents.llm.LLMAgent` that
    accepts ``input`` and ``prompt`` as keyword arguments with clean types.

    Parameters
    ----------
    name:
        Unique component name.
    model:
        An LLM component instance (e.g. ``OpenAI(...)``).
    tools:
        List of tool component instances (e.g. ``[MCP(...)]``).
    input:
        An optional input component (e.g. ``CommandLine(...)``).
    prompt:
        System prompt — either a :class:`~woodwork.primitives.File` reference,
        an inline ``str``, or a ``dict`` (legacy .ww format).
    """

    def __init__(
        self,
        name: str,
        model: Any,
        tools: Optional[List[Any]] = None,
        input: Optional[Any] = None,  # noqa: A002
        prompt: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            name=name,
            model=model,
            tools=tools or [],
            input=input,
            prompt=prompt,
            **kwargs,
        )


__all__ = ["Agent"]
