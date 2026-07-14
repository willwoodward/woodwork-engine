"""Core eval runner — boots agent config, runs cases, captures traces."""

import asyncio
import logging
import os
import time

from woodwork.eval.assertions import evaluate_assertions
from woodwork.eval.loader import EvalSuite
from woodwork.eval.report import CaseResult, EvalReport
from woodwork.eval.trace import TraceCollector
from woodwork.runtime.unified_event_bus import get_global_event_bus

log = logging.getLogger(__name__)


class EvalRunner:
    """Boots an agent from a .ww config and runs eval cases against it."""

    async def run(self, suite: EvalSuite) -> EvalReport:
        """Run all cases in the suite and return an EvalReport."""
        components, agent = self._boot(suite.config_path)

        await self._start_async(components)

        event_bus = get_global_event_bus()
        collector = TraceCollector()
        collector.register(event_bus)

        results: list[CaseResult] = []
        for case in suite.cases:
            collector.reset()
            start = time.time()
            try:
                response = await agent.input(case.input)
                if response is None:
                    response = ""
                else:
                    response = str(response)
            except Exception as e:
                log.error("Error running case '%s': %s", case.name, e)
                response = f"[ERROR] {e}"

            trace = collector.get_trace(response, time.time() - start)
            assertion_results = evaluate_assertions(trace, case.assertions)
            results.append(CaseResult(case=case, trace=trace, assertions=assertion_results))

        collector.unregister(event_bus)
        await self._cleanup(components)

        return EvalReport(results=results)

    def _boot(self, config_path: str) -> tuple:
        """Parse .ww config and return (components, agent).

        Reuses the existing parse pipeline: activate venv, parse config, get components.
        """
        import queue

        from woodwork.components.agents.llm import LLMAgent
        from woodwork.config import dependencies
        from woodwork.config import parser as config_parser
        from woodwork.config.factory import _get_task_master
        from woodwork.cli.progress.lifecycles import start_component

        config_dir = os.path.dirname(os.path.abspath(config_path))
        original_cwd = os.getcwd()

        try:
            os.chdir(config_dir)
            dependencies.activate_virtual_environment()
            config_parser.main_function()
            components = _get_task_master()._tools
        finally:
            os.chdir(original_cwd)

        # Sync-start all Startable components
        q = queue.Queue()
        for comp in components:
            try:
                start_component(comp, q)
            except Exception as e:
                log.warning("Failed to start component '%s': %s", getattr(comp, "name", "?"), e)

        # Find the agent
        agent = None
        for comp in components:
            if isinstance(comp, LLMAgent):
                agent = comp
                break

        if agent is None:
            raise RuntimeError(f"No LLMAgent found in config {config_path}")

        return components, agent

    async def _start_async(self, components: list) -> None:
        """Handle async startup (MCP servers with _blocking_startup_task)."""
        event_bus = get_global_event_bus()

        # Register components with event bus
        for comp in components:
            event_bus.register_component(comp)

        # Gather blocking startup tasks (MCP servers)
        tasks = []
        for comp in components:
            if hasattr(comp, "_blocking_startup_task") and comp._blocking_startup_task:
                tasks.append(comp._blocking_startup_task)

        if tasks:
            try:
                await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=30.0)
            except asyncio.TimeoutError:
                log.warning("Some async components did not start within 30 seconds")

        event_bus.configure_routing()

    async def _cleanup(self, components: list) -> None:
        """Close components and clean up."""
        for comp in components:
            try:
                if hasattr(comp, "close"):
                    if asyncio.iscoroutinefunction(comp.close):
                        await comp.close()
                    else:
                        comp.close()
            except Exception as e:
                log.debug("Error closing component '%s': %s", getattr(comp, "name", "?"), e)
