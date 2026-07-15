"""High-level Runtime class for the woodwork Python API.

Wraps :class:`~woodwork.core.runtime.AsyncRuntime` and provides two modes:

**Deployed** (blocking, with CLI/API main loop)::

    Runtime([model, search, cli, assistant]).init().start()

**Programmatic** (async context manager)::

    async with Runtime([model, search, assistant]) as rt:
        result = await assistant.send("What's the weather?")

    # Auto-discover components from a root agent:
    async with Runtime(assistant) as rt:
        result = await assistant.send("What's the weather?")
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Union

from woodwork.core.runtime import AsyncRuntime

log = logging.getLogger(__name__)


class Runtime:
    """Thin wrapper around :class:`~woodwork.core.runtime.AsyncRuntime`.

    Parameters
    ----------
    components:
        Either a list of component instances **or** a single root component
        (typically an Agent).  When a single component is given, the runtime
        auto-discovers its dependencies via a DFS traversal of
        ``_model_component``, ``_tools``, and ``_input_component``.
    """

    def __init__(self, components: Union[List[Any], Any]) -> None:
        if isinstance(components, list):
            self._components: List[Any] = components
        else:
            self._components = self._discover(components)
        self._async_runtime: Optional[AsyncRuntime] = None

    # ------------------------------------------------------------------ #
    # Component discovery                                                  #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _discover(root: Any) -> List[Any]:
        """DFS traversal from *root*, returning components in dependency order."""
        seen: set = set()
        result: List[Any] = []

        def visit(comp: Any) -> None:
            if comp is None or id(comp) in seen:
                return
            seen.add(id(comp))
            # Visit dependencies first so they initialise before the parent
            for dep in Runtime._get_deps(comp):
                visit(dep)
            result.append(comp)

        visit(root)
        return result

    @staticmethod
    def _get_deps(comp: Any) -> List[Any]:
        """Return the direct dependencies of *comp*."""
        deps: List[Any] = []
        for attr in ("_model_component", "_input_component"):
            val = getattr(comp, attr, None)
            if val is not None:
                deps.append(val)
        for tool in getattr(comp, "_tools", []):
            deps.append(tool)
        return deps

    def _build_dep_map(self) -> Dict[str, List[str]]:
        """Build the ``{name: [dep_names]}`` map for :class:`AsyncRuntime`."""
        dep_map: Dict[str, List[str]] = {}
        for comp in self._components:
            deps: List[str] = []
            for attr in ("_model_component", "_input_component"):
                val = getattr(comp, attr, None)
                if val is not None:
                    deps.append(val.name)
            for tool in getattr(comp, "_tools", []):
                deps.append(tool.name)
            dep_map[comp.name] = deps
        return dep_map

    # ------------------------------------------------------------------ #
    # Deployed mode (blocking)                                            #
    # ------------------------------------------------------------------ #

    def init(self, isolated: bool = False) -> "Runtime":
        """Install component dependencies into the project virtual environment.

        Returns *self* for chaining: ``Runtime(...).init().start()``.
        """
        from woodwork.config.dependencies import setup_virtual_env, get_requirements
        import tempfile
        import subprocess
        import os

        setup_virtual_env({"isolated": isolated})

        component_types = [(getattr(c, "component", ""), getattr(c, "type", "")) for c in self._components]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            get_requirements(component_types, tmp_path)
            activate = ".woodwork/env/bin/activate"
            subprocess.check_call(
                [f". {activate} && uv pip install -r {tmp_path}"],
                shell=True,
            )
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        return self

    def start(self) -> None:
        """Start the runtime in deployed mode (blocks until exit).

        Runs the main event loop (CLI input or API keep-alive).
        """
        dep_map = self._build_dep_map()
        asyncio.run(AsyncRuntime().start(self._components, dep_map))

    # ------------------------------------------------------------------ #
    # Programmatic mode (async context manager)                           #
    # ------------------------------------------------------------------ #

    async def __aenter__(self) -> "Runtime":
        dep_map = self._build_dep_map()
        self._async_runtime = AsyncRuntime()
        await self._async_runtime.setup(self._components, dep_map)
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._async_runtime is not None:
            await self._async_runtime._cleanup()
            self._async_runtime = None


__all__ = ["Runtime"]
