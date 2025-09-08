import asyncio
import inspect
import logging
import importlib.util
import os
from collections import defaultdict
from typing import Any, Callable, Dict, List

log = logging.getLogger(__name__)

Listener = Callable[[Any], Any]


class EventManager:
    """Unified event system with three concepts:

    - Events: fire-and-forget listeners (no return expected)
    - Hooks: async read-only listeners that run concurrently
    - Pipes: async transform functions that run sequentially and modify payloads
    
    All are triggered by a single emit() method that handles the orchestration.
    """

    def __init__(self) -> None:
        self._events: Dict[str, List[Listener]] = defaultdict(list)
        self._hooks: Dict[str, List[Listener]] = defaultdict(list) 
        self._pipes: Dict[str, List[Listener]] = defaultdict(list)

    # Event API (fire-and-forget)
    def on_event(self, event: str, listener: Listener) -> None:
        """Register a fire-and-forget event listener"""
        self._events[event].append(listener)
        log.debug(f"[EventManager] Registered EVENT listener for '{event}'. Total events for this event: {len(self._events[event])}")
    
    # Hook API (read-only, async)
    def on_hook(self, event: str, listener: Listener) -> None:
        """Register an async hook (read-only)"""
        self._hooks[event].append(listener)
        log.debug(f"[EventManager] Registered HOOK listener for '{event}'. Total hooks for this event: {len(self._hooks[event])}")
    
    # Pipe API (transform payload)
    def on_pipe(self, event: str, listener: Listener) -> None:
        """Register an async pipe (transform payload)"""
        self._pipes[event].append(listener)
        log.debug(f"[EventManager] Registered PIPE listener for '{event}'. Total pipes for this event: {len(self._pipes[event])}")
    
    # Removal methods
    def off(self, event: str, listener: Listener) -> None:
        """Remove a listener from events, hooks, or pipes"""
        for collection in [self._events, self._hooks, self._pipes]:
            if listener in collection.get(event, []):
                collection[event].remove(listener)

    async def emit(self, event: str, payload: Any = None) -> Any:
        """Unified emit method that handles events, hooks, and pipes in sequence"""
        log.debug(f"[EventManager] Emitting event '{event}' with payload type: {type(payload)}")
        
        # Check what listeners we have for this event
        num_events = len(self._events[event])
        num_hooks = len(self._hooks[event]) 
        num_pipes = len(self._pipes[event])
        log.debug(f"[EventManager] Event '{event}' has {num_events} events, {num_hooks} hooks, {num_pipes} pipes")
        
        # 1. Events (fire-and-forget, not awaited)
        for i, listener in enumerate(self._events[event]):
            try:
                log.debug(f"[EventManager] Executing event listener {i+1}/{num_events} for '{event}'")
                if inspect.iscoroutinefunction(listener):
                    asyncio.create_task(listener(payload))
                else:
                    listener(payload)
            except Exception as e:
                log.exception(f"[event error] Event listener {i+1} failed for '{event}': {e}")

        # 2. Hooks (await all concurrently)  
        hook_tasks = []
        for i, hook in enumerate(self._hooks[event]):
            log.debug(f"[EventManager] Preparing hook {i+1}/{num_hooks} for '{event}'")
            if inspect.iscoroutinefunction(hook):
                hook_tasks.append(self._safe_call_async(hook, payload, event))
            else:
                # Wrap sync function in async with proper closure
                hook_tasks.append(self._wrap_sync_call(hook, payload, event))
        
        if hook_tasks:
            log.debug(f"[EventManager] Executing {len(hook_tasks)} hooks concurrently for '{event}'")
            await asyncio.gather(*hook_tasks, return_exceptions=True)

        # 3. Pipes (chain sequentially)
        current_payload = payload
        for i, pipe in enumerate(self._pipes[event]):
            try:
                log.debug(f"[EventManager] Executing pipe {i+1}/{num_pipes} for '{event}'")
                if inspect.iscoroutinefunction(pipe):
                    result = await pipe(current_payload)
                else:
                    result = pipe(current_payload)
                
                if result is not None:
                    log.debug(f"[EventManager] Pipe {i+1} transformed payload for '{event}'")
                    current_payload = result
                else:
                    log.debug(f"[EventManager] Pipe {i+1} returned None, keeping original payload for '{event}'")
            except Exception as e:
                log.exception(f"[pipe error] Pipe {i+1} failed for '{event}': {e}")
        
        log.debug(f"[EventManager] Finished emitting '{event}', returning payload type: {type(current_payload)}")
        return current_payload

    async def _safe_call_async(self, listener: Listener, payload: Any, event: str) -> None:
        """Safely call an async listener with error handling"""
        try:
            await listener(payload)
        except Exception as e:
            log.exception(f"[hook error] {e}")
    
    async def _wrap_sync_call(self, listener: Listener, payload: Any, event: str) -> None:
        """Wrap a sync call for use in async context"""
        try:
            listener(payload)
        except Exception as e:
            log.exception(f"[hook error] {e}")

    # Configuration-based registration methods
    def load_script_function(self, script_path: str, function_name: str) -> Callable:
        """Load a function from a Python script file"""
        try:
            # Convert relative path to absolute if needed
            if not os.path.isabs(script_path):
                script_path = os.path.abspath(script_path)
            
            spec = importlib.util.spec_from_file_location("dynamic_module", script_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot load module from {script_path}")
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            if not hasattr(module, function_name):
                raise AttributeError(f"Function '{function_name}' not found in {script_path}")
            
            return getattr(module, function_name)
        except Exception as e:
            log.error(f"Failed to load function {function_name} from {script_path}: {e}")
            raise
    
    def register_hook_from_config(self, event: str, script_path: str, function_name: str) -> None:
        """Register a hook from configuration"""
        log.debug(f"[EventManager] Loading hook {function_name} from {script_path} for event '{event}'")
        func = self.load_script_function(script_path, function_name)
        self.on_hook(event, func)
        log.debug(f"[EventManager] Successfully registered hook {function_name} for event '{event}'")
    
    def register_pipe_from_config(self, event: str, script_path: str, function_name: str) -> None:
        """Register a pipe from configuration"""
        log.debug(f"[EventManager] Loading pipe {function_name} from {script_path} for event '{event}'")
        func = self.load_script_function(script_path, function_name)
        self.on_pipe(event, func)
        log.debug(f"[EventManager] Successfully registered pipe {function_name} for event '{event}'")
    
    def register_event_from_config(self, event: str, script_path: str, function_name: str) -> None:
        """Register an event listener from configuration"""
        log.debug(f"[EventManager] Loading event listener {function_name} from {script_path} for event '{event}'")
        func = self.load_script_function(script_path, function_name)
        self.on_event(event, func)
        log.debug(f"[EventManager] Successfully registered event listener {function_name} for event '{event}'")

    # Synchronous convenience method
    def emit_sync(self, event: str, payload: Any = None) -> Any:
        """Emit events, hooks, and pipes synchronously - much simpler!"""
        log.debug(f"[EventManager] emit_sync called for event '{event}'")
        
        # Check what listeners we have
        num_events = len(self._events[event])
        num_hooks = len(self._hooks[event]) 
        num_pipes = len(self._pipes[event])
        log.debug(f"[EventManager] Event '{event}' has {num_events} events, {num_hooks} hooks, {num_pipes} pipes")
        
        if num_events == 0 and num_hooks == 0 and num_pipes == 0:
            return payload
        
        # 1. Events (fire-and-forget)
        for i, listener in enumerate(self._events[event]):
            try:
                log.debug(f"[EventManager] Executing event listener {i+1} for '{event}'")
                if inspect.iscoroutinefunction(listener):
                    # For async functions, run them synchronously 
                    try:
                        loop = asyncio.get_running_loop()
                        # We're in an async context, but let's be simple and skip async events for now
                        log.warning(f"[EventManager] Skipping async event listener for '{event}' in sync context")
                        continue
                    except RuntimeError:
                        # No loop, we can run it
                        asyncio.run(listener(payload))
                else:
                    listener(payload)
            except Exception as e:
                log.exception(f"[EventManager] Event listener {i+1} failed for '{event}': {e}")

        # 2. Hooks (run all synchronously)
        for i, hook in enumerate(self._hooks[event]):
            try:
                log.debug(f"[EventManager] Executing hook {i+1} for '{event}'")
                if inspect.iscoroutinefunction(hook):
                    # For async hooks, run them synchronously
                    try:
                        loop = asyncio.get_running_loop()
                        # We're in an async context, but let's be simple and skip async hooks for now
                        log.warning(f"[EventManager] Skipping async hook for '{event}' in sync context")
                        continue
                    except RuntimeError:
                        # No loop, we can run it
                        asyncio.run(hook(payload))
                else:
                    hook(payload)
            except Exception as e:
                log.exception(f"[EventManager] Hook {i+1} failed for '{event}': {e}")

        # 3. Pipes (run sequentially, transform payload)
        current_payload = payload
        for i, pipe in enumerate(self._pipes[event]):
            try:
                log.debug(f"[EventManager] Executing pipe {i+1} for '{event}'")
                if inspect.iscoroutinefunction(pipe):
                    # For async pipes, run them synchronously
                    try:
                        loop = asyncio.get_running_loop()
                        log.warning(f"[EventManager] Skipping async pipe for '{event}' in sync context")
                        continue
                    except RuntimeError:
                        result = asyncio.run(pipe(current_payload))
                        if result is not None:
                            current_payload = result
                else:
                    result = pipe(current_payload)
                    if result is not None:
                        current_payload = result
            except Exception as e:
                log.exception(f"[EventManager] Pipe {i+1} failed for '{event}': {e}")

        log.debug(f"[EventManager] Finished emitting '{event}' synchronously")
        return current_payload


# Global event manager instance
_global_event_manager = None

def get_global_event_manager() -> EventManager:
    """Get the global event manager instance"""
    global _global_event_manager
    if _global_event_manager is None:
        _global_event_manager = EventManager()
    return _global_event_manager

def set_global_event_manager(manager: EventManager) -> None:
    """Set the global event manager instance"""
    global _global_event_manager
    _global_event_manager = manager

# Super simple global functions that components can use
def emit(event: str, payload: Any = None) -> Any:
    """Emit an event through the global event manager - super simple with built-in error handling!"""
    try:
        return get_global_event_manager().emit_sync(event, payload)
    except Exception as e:
        log.exception(f"Error emitting event '{event}': {e}")
        # Return original payload on error so the caller can continue
        return payload

def register_hook(event: str, script_path: str, function_name: str) -> None:
    """Register a hook globally - super simple!"""
    get_global_event_manager().register_hook_from_config(event, script_path, function_name)

def register_pipe(event: str, script_path: str, function_name: str) -> None:
    """Register a pipe globally - super simple!"""
    get_global_event_manager().register_pipe_from_config(event, script_path, function_name)

# Convenience factory
def create_default_emitter() -> EventManager:
    return EventManager()