"""
AsyncRuntime — clean orchestrator for woodwork components.

Replaces the old runtime/async_runtime.py + task_master.py.
Responsibilities:
  - Accept a flat list of components + a dependency map.
  - Initialize and start components in dependency order.
  - Run the main loop (CLI input or API keep-alive).
  - Graceful shutdown.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from woodwork.core.events import EventBus

log = logging.getLogger(__name__)


class AsyncRuntime:
    """
    Orchestrates component lifecycle and the main event loop.

    Usage::

        runtime = AsyncRuntime()
        await runtime.start(components, dep_map)
    """

    def __init__(self, system_bus: Optional[EventBus] = None) -> None:
        self.system_bus: EventBus = system_bus or EventBus()
        self._components: Dict[str, Any] = {}
        self._running = False
        self._api_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------ #
    # Public entry point                                                   #
    # ------------------------------------------------------------------ #

    async def start(self, components: List[Any], dep_map: Optional[Dict[str, List[str]]] = None) -> None:
        """
        Start the runtime with *components* (already constructed).

        *dep_map* maps component name → list of names it depends on.
        """
        dep_map = dep_map or {}
        self._running = True

        # Register
        for comp in components:
            self._components[comp.name] = comp

        # Initialize in dependency order
        ordered = self._topo_sort(components, dep_map)
        await self._initialize_all(ordered)

        # Start
        await self._start_all(ordered)

        # Enter main loop
        try:
            await self._main_loop()
        finally:
            await self._cleanup()

    async def setup(self, components: List[Any], dep_map: Optional[Dict[str, List[str]]] = None) -> None:
        """Initialise and start *components* without entering the main loop.

        Used by :class:`woodwork.runtime.Runtime` as an async context manager
        so callers can send queries programmatically.
        """
        dep_map = dep_map or {}
        self._running = True

        for comp in components:
            self._components[comp.name] = comp

        ordered = self._topo_sort(components, dep_map)
        await self._initialize_all(ordered)
        await self._start_all(ordered)

    async def stop(self) -> None:
        self._running = False
        if self._api_task and not self._api_task.done():
            self._api_task.cancel()
            try:
                await self._api_task
            except asyncio.CancelledError:
                pass

    # ------------------------------------------------------------------ #
    # Lifecycle helpers                                                    #
    # ------------------------------------------------------------------ #

    async def _initialize_all(self, components: List[Any]) -> None:
        for comp in components:
            if hasattr(comp, "initialize"):
                try:
                    fn = comp.initialize
                    if asyncio.iscoroutinefunction(fn):
                        await fn()
                    else:
                        fn()
                    log.debug("[AsyncRuntime] Initialized '%s'", comp.name)
                except Exception as exc:
                    log.error("[AsyncRuntime] Error initializing '%s': %s", comp.name, exc)

    async def _start_all(self, components: List[Any]) -> None:
        tasks = []
        for comp in components:
            if hasattr(comp, "start"):
                fn = comp.start
                if asyncio.iscoroutinefunction(fn):
                    tasks.append(asyncio.create_task(fn(), name=f"start-{comp.name}"))
                else:
                    try:
                        fn()
                        log.debug("[AsyncRuntime] Started (sync) '%s'", comp.name)
                    except Exception as exc:
                        log.error("[AsyncRuntime] Error starting '%s': %s", comp.name, exc)
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for comp, result in zip([c for c in components if hasattr(c, "start") and asyncio.iscoroutinefunction(c.start)], results):
                if isinstance(result, Exception):
                    log.error("[AsyncRuntime] Error starting '%s': %s", comp.name, result)

    async def _cleanup(self) -> None:
        # Temporarily suspend pending task cancellations (Python 3.11+).
        # Without this, every `await` inside a finally-driven cleanup raises
        # CancelledError immediately, leaving sessions / connections open.
        task = asyncio.current_task()
        cancelling = task.cancelling() if task is not None else 0
        for _ in range(cancelling):
            task.uncancel()

        try:
            for comp in self._components.values():
                for method in ("stop", "close"):
                    fn = getattr(comp, method, None)
                    if fn is None:
                        continue
                    try:
                        if asyncio.iscoroutinefunction(fn):
                            await fn()
                        else:
                            fn()
                    except Exception as exc:
                        log.debug("[AsyncRuntime] Error stopping '%s': %s", getattr(comp, "name", "?"), exc)
                    break  # only call the first available method
        finally:
            # Restore the cancellation counter so the task resumes cancelling
            # normally after cleanup finishes.
            for _ in range(cancelling):
                task.cancel()

    # ------------------------------------------------------------------ #
    # Main loop                                                            #
    # ------------------------------------------------------------------ #

    async def _main_loop(self) -> None:
        api_comp = self._find_api_component()
        if api_comp:
            await self._run_api(api_comp)
        else:
            await self._run_cli()

    def _find_api_component(self) -> Optional[Any]:
        for comp in self._components.values():
            if hasattr(comp, "start_server"):
                return comp
        return None

    def _find_input_component(self) -> Optional[Any]:
        for comp in self._components.values():
            if hasattr(comp, "stream"):
                return comp
            if hasattr(comp, "input_function"):
                return comp
        return None

    def _find_agent_component(self) -> Optional[Any]:
        for comp in self._components.values():
            if hasattr(comp, "execute") and getattr(comp, "component", "") == "agent":
                return comp
        return None

    async def _run_api(self, api_comp: Any) -> None:
        log.info("[AsyncRuntime] Starting API server")
        self._api_task = asyncio.create_task(api_comp.start_server())
        try:
            await self._api_task
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            log.error("[AsyncRuntime] API server error: %s", exc)

    async def _run_cli(self) -> None:
        log.info("[AsyncRuntime] Starting CLI input loop")
        input_comp = self._find_input_component()
        agent_comp = self._find_agent_component()

        if not input_comp or not agent_comp:
            log.warning("[AsyncRuntime] No input/agent pair found; runtime will idle")
            while self._running:
                await asyncio.sleep(1)
            return

        loop = asyncio.get_running_loop()
        try:
            if hasattr(input_comp, "stream"):
                # New stream() API — loop is driven by the generator lifetime
                async for query in input_comp.stream():
                    if not self._running:
                        break
                    if query in ("exit", ";"):
                        self._running = False
                        break
                    result = await agent_comp.execute("run", {"query": query})
                    await input_comp.respond(result)
            elif hasattr(input_comp, "input_function"):
                # Legacy blocking input
                while self._running:
                    query = await loop.run_in_executor(None, input_comp.input_function)
                    if query in ("exit", ";"):
                        break
                    result = await agent_comp.execute("run", {"query": query})
                    print(result)
            else:
                while self._running:
                    await asyncio.sleep(1)
        except KeyboardInterrupt:
            self._running = False

    # ------------------------------------------------------------------ #
    # Dependency sort                                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _topo_sort(components: List[Any], dep_map: Dict[str, List[str]]) -> List[Any]:
        """
        Return components in an order where dependencies come first.
        Cycles are broken arbitrarily (logged as warnings).
        """
        by_name = {c.name: c for c in components}
        visited: set[str] = set()
        result: List[Any] = []

        def visit(name: str, stack: set[str]) -> None:
            if name in visited:
                return
            if name in stack:
                log.warning("[AsyncRuntime] Dependency cycle detected at '%s'", name)
                return
            stack.add(name)
            for dep in dep_map.get(name, []):
                if dep in by_name:
                    visit(dep, stack)
            stack.discard(name)
            visited.add(name)
            if name in by_name:
                result.append(by_name[name])

        for comp in components:
            visit(comp.name, set())

        return result
