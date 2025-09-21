"""
Async Runtime - Single async event loop for all components

This replaces distributed startup threading with a unified async runtime
that eliminates cross-thread communication and provides real-time event delivery.
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional

from woodwork.core.unified_event_bus import UnifiedEventBus, get_global_event_bus
from woodwork.types import InputReceivedPayload

log = logging.getLogger(__name__)


class AsyncRuntime:
    """
    Unified async runtime for all components.

    Replaces distributed startup threading with single async context.
    All components run in the same event loop for real-time communication.
    """

    def __init__(self):
        self.event_bus = get_global_event_bus()
        self.components: Dict[str, Any] = {}
        self.config: Dict[str, Any] = {}
        self._running = False
        self._api_server_task: Optional[asyncio.Task] = None

        log.debug("[AsyncRuntime] Initialized")

    async def start(self, config: Dict[str, Any]) -> None:
        """
        Start async runtime with component configuration.

        All components run in single async context - no threading.
        """
        log.info("[AsyncRuntime] Starting with %d component configs", len(config))

        self.config = config
        self._running = True

        try:
            # 1. Parse and register components
            await self.initialize_components(config)

            # 2. Configure routing
            self.event_bus.configure_routing()

            # 3. Start API server if needed (in same async context)
            if self.has_api_component():
                await self._start_api_server()

            # 4. Start main event loop
            await self._main_loop()

        except Exception as e:
            log.error("[AsyncRuntime] Error during startup: %s", e)
            raise
        finally:
            await self._cleanup()

    async def initialize_components(self, config: Dict[str, Any]) -> None:
        """Parse and register components from configuration"""
        log.debug("[AsyncRuntime] Initializing components from config")

        # Parse components using existing parser
        components = await self._parse_components(config)

        # Register with event bus
        for component in components:
            self.event_bus.register_component(component)
            self.components[component.name] = component

        log.info("[AsyncRuntime] Initialized %d components", len(components))

    async def _parse_components(self, config: Dict[str, Any]) -> List[Any]:
        """Parse components from configuration"""
        try:
            # If config already has components list, use it directly
            if "components" in config and isinstance(config["components"], list):
                return config["components"]

            # If config has component_configs, extract components
            if "component_configs" in config:
                components = []
                for comp_config in config["component_configs"].values():
                    if "object" in comp_config:
                        components.append(comp_config["object"])
                return components

            # Use existing config parser for dictionary configs
            from woodwork.parser.config_parser import parse_config_dict
            parsed = parse_config_dict(config)
            return parsed.get('components', [])

        except Exception as e:
            log.error("[AsyncRuntime] Error parsing components: %s", e)
            # Return empty list rather than mock components
            return []

    def has_api_component(self) -> bool:
        """Check if any component is an API input component"""
        for component in self.components.values():
            if hasattr(component, '__class__') and 'api' in component.__class__.__name__.lower():
                return True
        return False

    async def _start_api_server(self) -> None:
        """Start API server in same async context"""
        log.info("[AsyncRuntime] Starting API server in async context")

        # Find API component
        api_component = None
        for component in self.components.values():
            if hasattr(component, '__class__') and 'api' in component.__class__.__name__.lower():
                api_component = component
                break

        if not api_component:
            log.warning("[AsyncRuntime] API component not found")
            return

        # Start API server as async task
        self._api_server_task = asyncio.create_task(
            self._run_api_server(api_component)
        )

        log.info("[AsyncRuntime] API server task created")

    async def _run_api_server(self, api_component: Any) -> None:
        """Run API server for the component"""
        try:
            if hasattr(api_component, 'start_server'):
                await api_component.start_server()
            else:
                log.warning("[AsyncRuntime] API component has no start_server method")
        except Exception as e:
            log.error("[AsyncRuntime] API server error: %s", e)

    async def _main_loop(self) -> None:
        """Main async event loop"""
        log.info("[AsyncRuntime] Starting main event loop")

        # Check if we have API component (handles own input)
        if self.has_api_component():
            # For API components, just keep runtime alive
            await self._keep_alive_for_api()
        else:
            # For non-API components, handle input loop
            await self._input_loop()

    async def _keep_alive_for_api(self) -> None:
        """Keep runtime alive for API components"""
        log.info("[AsyncRuntime] Keeping runtime alive for API components")

        try:
            while self._running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            log.info("[AsyncRuntime] Shutdown signal received")
            self._running = False

    async def _input_loop(self) -> None:
        """Input loop for non-API components"""
        log.info("[AsyncRuntime] Starting input loop for non-API components")

        # Find input component
        input_component = None
        for component in self.components.values():
            if hasattr(component, 'input_function'):
                input_component = component
                break

        if not input_component:
            log.warning("[AsyncRuntime] No input component found")
            return

        try:
            while self._running:
                # Get input (this should be async or made async)
                user_input = await self._get_user_input(input_component)

                if user_input in ["exit", ";"]:
                    break

                # Process input through event system
                await self.process_user_input(user_input, input_component.name)

        except KeyboardInterrupt:
            log.info("[AsyncRuntime] Input loop interrupted")
        except Exception as e:
            log.error("[AsyncRuntime] Error in input loop: %s", e)

    async def _get_user_input(self, input_component: Any) -> str:
        """Get user input asynchronously"""
        try:
            # If input_function is sync, run in executor
            if hasattr(input_component, 'input_function'):
                if asyncio.iscoroutinefunction(input_component.input_function):
                    return await input_component.input_function()
                else:
                    # Run sync function in thread pool
                    loop = asyncio.get_running_loop()
                    return await loop.run_in_executor(None, input_component.input_function)
            else:
                # Fallback to basic input
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(None, input, "Enter input: ")
        except Exception as e:
            log.error("[AsyncRuntime] Error getting user input: %s", e)
            return ""

    async def process_user_input(self, user_input: str, source_component: str) -> None:
        """Process user input through unified event system"""
        log.debug("[AsyncRuntime] Processing user input: %s", user_input[:100])

        # Create input payload
        payload = InputReceivedPayload(
            input=user_input,
            inputs={},
            session_id="default_session",
            component_id=source_component,
            component_type="inputs"
        )

        # Emit through unified event bus
        await self.event_bus.emit_from_component(source_component, "input.received", payload)

    async def process_component_input(self, component: Any, input_data: Any) -> Any:
        """Process input directly to component (for testing)"""
        if hasattr(component, 'input'):
            if asyncio.iscoroutinefunction(component.input):
                return await component.input(input_data)
            else:
                # Run sync input in executor
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(None, component.input, input_data)
        return None

    async def stop(self) -> None:
        """Stop the runtime"""
        log.info("[AsyncRuntime] Stopping runtime")
        self._running = False

        # Stop API server task
        if self._api_server_task and not self._api_server_task.done():
            self._api_server_task.cancel()
            try:
                await self._api_server_task
            except asyncio.CancelledError:
                pass

        await self._cleanup()

    async def _cleanup(self) -> None:
        """Clean up resources"""
        log.debug("[AsyncRuntime] Cleaning up resources")

        # Close components
        for component in self.components.values():
            try:
                if hasattr(component, 'close') and asyncio.iscoroutinefunction(component.close):
                    await component.close()
                elif hasattr(component, 'close'):
                    component.close()
            except Exception as e:
                log.error("[AsyncRuntime] Error closing component %s: %s", getattr(component, 'name', 'unknown'), e)

        log.info("[AsyncRuntime] Cleanup completed")

    def get_stats(self) -> Dict[str, Any]:
        """Get runtime statistics"""
        return {
            "running": self._running,
            "components_count": len(self.components),
            "has_api_component": self.has_api_component(),
            "api_server_running": self._api_server_task is not None and not self._api_server_task.done(),
            "event_bus_stats": self.event_bus.get_stats()
        }


# Global runtime instance
_global_runtime: Optional[AsyncRuntime] = None


def get_global_runtime() -> AsyncRuntime:
    """Get or create global async runtime"""
    global _global_runtime

    if _global_runtime is None:
        _global_runtime = AsyncRuntime()
        log.info("[AsyncRuntime] Created global runtime instance")

    return _global_runtime


def set_global_runtime(runtime: AsyncRuntime) -> None:
    """Set custom global runtime"""
    global _global_runtime
    _global_runtime = runtime
    log.info("[AsyncRuntime] Set custom global runtime")


async def start_runtime(config: Dict[str, Any]) -> None:
    """Start the global runtime"""
    runtime = get_global_runtime()
    await runtime.start(config)


async def stop_runtime() -> None:
    """Stop the global runtime"""
    global _global_runtime
    if _global_runtime:
        await _global_runtime.stop()
        _global_runtime = None