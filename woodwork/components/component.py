"""
Base Component class.

Stripped of MessageBusIntegration and StreamingMixin.
All components share: name, config, lifecycle hooks, and hook/pipe registration.
"""

import logging
import importlib.util
import os
from typing import Any, Callable, Dict, List, Optional

from woodwork.core.events import EventBus
from woodwork.interfaces.stoppable import Stoppable
from woodwork.types.workflows import Hook, Pipe

log = logging.getLogger(__name__)


class Component(Stoppable):
    """
    Minimal base class for all woodwork components.

    Subclasses add domain logic (LLM calls, API requests, …) and may mix
    in StreamingMixin if they need streaming I/O.
    """

    def __init__(self, name: str, component: str, type: str, **config: Any) -> None:
        self.name = name
        self.component = component
        self.type = type
        self.config = config

        # Per-component event bus (LLMAgent overrides with a bus that has a parent)
        self.event_bus: EventBus = EventBus()

        # Hook / pipe configs parsed from the .ww file (list-of-dicts path)
        self._hook_configs: List[Hook] = self._parse_hooks(
            config.get("hooks") if isinstance(config.get("hooks"), list) else []
        )
        self._pipe_configs: List[Pipe] = self._parse_pipes(
            config.get("pipes") if isinstance(config.get("pipes"), list) else []
        )

        # Python API: hooks/pipes passed as {event: callable} dicts
        if isinstance(config.get("hooks"), dict):
            for event, fn in config["hooks"].items():
                self.event_bus.register_hook(event if isinstance(event, str) else str(event), fn)
        if isinstance(config.get("pipes"), dict):
            for event, fn in config["pipes"].items():
                self.event_bus.register_pipe(event if isinstance(event, str) else str(event), fn)

        log.debug("[Component] Initialized '%s' (component=%s type=%s)", name, component, type)

    # ------------------------------------------------------------------ #
    # Lifecycle (no-op defaults — subclasses override as needed)          #
    # ------------------------------------------------------------------ #

    def initialize(self) -> None:
        """Synchronous pre-start initialisation (e.g. pulling Ollama model)."""

    async def start(self) -> None:
        """Async start (e.g. connecting to a service)."""

    async def stop(self) -> None:
        """Async teardown."""

    def close(self) -> None:
        """Synchronous cleanup (backwards-compat alias for stop)."""

    # ------------------------------------------------------------------ #
    # Execute — override in tool / agent components                       #
    # ------------------------------------------------------------------ #

    async def execute(self, action: str, inputs: Dict[str, Any]) -> Any:
        raise NotImplementedError(f"{self.__class__.__name__} does not implement execute()")

    # ------------------------------------------------------------------ #
    # Python API: hook / pipe decorators                                  #
    # ------------------------------------------------------------------ #

    def hook(self, event: Any) -> Callable:
        """Decorator: register a read-only hook for *event* on this component's bus.

        Usage::

            @component.hook(Event.Agent.TOOL_CALL)
            def on_tool_call(payload): ...
        """
        event_str = event if isinstance(event, str) else str(event)

        def decorator(fn: Callable) -> Callable:
            self.event_bus.register_hook(event_str, fn)
            return fn

        return decorator

    def pipe(self, event: Any) -> Callable:
        """Decorator: register a transforming pipe for *event* on this component's bus.

        Usage::

            @component.pipe(Event.Agent.ACTION)
            def transform(payload): ...
        """
        event_str = event if isinstance(event, str) else str(event)

        def decorator(fn: Callable) -> Callable:
            self.event_bus.register_pipe(event_str, fn)
            return fn

        return decorator

    # ------------------------------------------------------------------ #
    # Hook / pipe wiring                                                  #
    # ------------------------------------------------------------------ #

    def _register_hooks_pipes(self, event_bus: Any) -> None:
        """Register all configured hooks and pipes on *event_bus*."""
        for hook in self._hook_configs:
            fn = self._load_function(hook.script_path, hook.function_name)
            if fn:
                event_bus.register_hook(hook.event, fn)
                log.debug("[Component %s] Registered hook '%s' on '%s'", self.name, hook.function_name, hook.event)

        for pipe in self._pipe_configs:
            fn = self._load_function(pipe.script_path, pipe.function_name)
            if fn:
                event_bus.register_pipe(pipe.event, fn)
                log.debug("[Component %s] Registered pipe '%s' on '%s'", self.name, pipe.function_name, pipe.event)

    # ------------------------------------------------------------------ #
    # Config parsers                                                      #
    # ------------------------------------------------------------------ #

    def _parse_hooks(self, hooks_config: List[Dict[str, Any]]) -> List[Hook]:
        result = []
        for cfg in hooks_config:
            try:
                result.append(Hook.from_dict(cfg))
            except Exception as exc:
                log.warning("[Component %s] Invalid hook config %s: %s", self.name, cfg, exc)
        return result

    def _parse_pipes(self, pipes_config: List[Dict[str, Any]]) -> List[Pipe]:
        result = []
        for cfg in pipes_config:
            try:
                result.append(Pipe.from_dict(cfg))
            except Exception as exc:
                log.warning("[Component %s] Invalid pipe config %s: %s", self.name, cfg, exc)
        return result

    # ------------------------------------------------------------------ #
    # Dynamic function loader (used by hooks/pipes)                       #
    # ------------------------------------------------------------------ #

    def _load_function(self, script_path: str, function_name: str) -> Optional[Any]:
        """Load *function_name* from *script_path* (abs or cwd-relative)."""
        try:
            if not os.path.isabs(script_path):
                abs_path = os.path.abspath(script_path) if os.path.exists(script_path) else script_path
            else:
                abs_path = script_path

            if not os.path.exists(abs_path):
                log.warning("[Component %s] Script not found: %s", self.name, abs_path)
                return None

            spec = importlib.util.spec_from_file_location("_dynamic", abs_path)
            if spec is None or spec.loader is None:
                log.warning("[Component %s] Cannot load spec from %s", self.name, abs_path)
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore[union-attr]

            fn = getattr(module, function_name, None)
            if fn is None:
                log.warning("[Component %s] Function '%s' not in %s", self.name, function_name, abs_path)
            return fn

        except Exception as exc:
            log.error("[Component %s] Error loading %s from %s: %s", self.name, function_name, script_path, exc)
            return None
