"""Lightweight EventBus with optional parent-bubbling for observability."""

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)


class EventBus:
    """
    Per-agent event bus that optionally bubbles events to a parent bus.

    Hooks  — concurrent, read-only listeners (debugging / logging).
    Pipes  — sequential, transforming listeners (can modify payloads).
    Events — fire-and-forget listeners (no return expected).

    Child buses bubble every emission to their parent so a single
    system-level bus can observe all agents without shared mutable state.
    """

    def __init__(self, parent: Optional["EventBus"] = None) -> None:
        self._hooks: Dict[str, List[Callable]] = defaultdict(list)
        self._pipes: Dict[str, List[Callable]] = defaultdict(list)
        self._events: Dict[str, List[Callable]] = defaultdict(list)
        self._parent = parent

    # ------------------------------------------------------------------ #
    # Registration                                                         #
    # ------------------------------------------------------------------ #

    def register_hook(self, event: str, fn: Callable) -> None:
        """Register a concurrent, read-only hook for *event*."""
        self._hooks[event].append(fn)

    def register_pipe(self, event: str, fn: Callable) -> None:
        """Register a sequential, transforming pipe for *event*."""
        self._pipes[event].append(fn)

    def register_event(self, event: str, fn: Callable) -> None:
        """Register a fire-and-forget listener for *event*."""
        self._events[event].append(fn)

    # ------------------------------------------------------------------ #
    # Emission                                                             #
    # ------------------------------------------------------------------ #

    async def emit(self, event: str, payload: Any) -> Any:
        """
        Emit *event* with *payload*.

        Processing order:
          1. Hooks run concurrently (read-only).
          2. Pipes run sequentially (may return a new payload).
          3. Fire-and-forget event listeners are scheduled.
          4. Event bubbles to parent (if any).

        Returns the (possibly pipe-transformed) payload.
        """
        # 1. Hooks — concurrent
        await self._run_hooks(event, payload)

        # 2. Pipes — sequential, may transform
        payload = await self._run_pipes(event, payload)

        # 3. Fire-and-forget listeners
        self._fire_events(event, payload)

        # 4. Bubble to parent
        if self._parent is not None:
            await self._parent.emit(event, payload)

        return payload

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    async def _run_hooks(self, event: str, payload: Any) -> None:
        hooks = self._hooks.get(event, [])
        if not hooks:
            return
        tasks = []
        for fn in hooks:
            try:
                if asyncio.iscoroutinefunction(fn):
                    tasks.append(fn(payload))
                else:
                    tasks.append(asyncio.get_event_loop().run_in_executor(None, fn, payload))
            except Exception as exc:
                log.error("[EventBus] Hook setup error for '%s': %s", event, exc)
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    log.error("[EventBus] Hook %d failed for '%s': %s", i, event, result)

    async def _run_pipes(self, event: str, payload: Any) -> Any:
        for fn in self._pipes.get(event, []):
            try:
                result = await fn(payload) if asyncio.iscoroutinefunction(fn) else fn(payload)
                if result is not None:
                    payload = result
            except Exception as exc:
                log.error("[EventBus] Pipe failed for '%s': %s", event, exc)
        return payload

    def _fire_events(self, event: str, payload: Any) -> None:
        for fn in self._events.get(event, []):
            try:
                if asyncio.iscoroutinefunction(fn):
                    asyncio.create_task(fn(payload))
                else:
                    fn(payload)
            except Exception as exc:
                log.error("[EventBus] Event listener failed for '%s': %s", event, exc)

    # ------------------------------------------------------------------ #
    # Introspection                                                        #
    # ------------------------------------------------------------------ #

    def stats(self) -> Dict[str, int]:
        return {
            "hooks": sum(len(v) for v in self._hooks.values()),
            "pipes": sum(len(v) for v in self._pipes.values()),
            "events": sum(len(v) for v in self._events.values()),
        }
