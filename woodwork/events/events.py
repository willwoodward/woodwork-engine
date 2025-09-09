import asyncio
import inspect
import logging
import importlib.util
import os
from collections import defaultdict
from typing import Any, Callable, Dict, List, Union

log = logging.getLogger(__name__)

Listener = Callable[[Any], Any]


class EventManager:
    """JSON-first event system with typed payloads:

    - Events: fire-and-forget listeners 
    - Hooks: read-only listeners that run concurrently
    - Pipes: transform functions that run sequentially and modify payloads
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

    def _execute_listener(self, listener: Listener, payload: Any, event: str, listener_type: str):
        """Execute listener with error handling"""
        try:
            if inspect.iscoroutinefunction(listener):
                if listener_type == "event":
                    asyncio.create_task(listener(payload))
                else:
                    return listener(payload)  # Return coroutine for await
            else:
                return listener(payload)
        except Exception as e:
            log.exception(f"{listener_type.capitalize()} failed for '{event}': {e}")

    async def emit(self, event: str, data: Any = None) -> Any:
        """Emit event with typed payload"""
        payload = self._create_typed_payload(event, data)
        
        # 1. Fire events (no await)
        for listener in self._events[event]:
            self._execute_listener(listener, payload, event, "event")

        # 2. Run hooks concurrently
        hook_tasks = [
            self._execute_listener(hook, payload, event, "hook") 
            for hook in self._hooks[event]
        ]
        hook_tasks = [t for t in hook_tasks if t is not None]  # Filter out None
        if hook_tasks:
            await asyncio.gather(*hook_tasks, return_exceptions=True)

        # 3. Chain pipes sequentially
        current_payload = payload
        for pipe in self._pipes[event]:
            result = self._execute_listener(pipe, current_payload, event, "pipe")
            if inspect.iscoroutinefunction(pipe):
                result = await result
            if result is not None:
                current_payload = result
        
        return current_payload

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

    def _create_typed_payload(self, event: str, data: Any) -> Any:
        """Create typed payload with component context"""
        from woodwork.types.events import PayloadRegistry
        from woodwork.types.event_source import EventSource
        
        # Get current component context
        context = EventSource.get_current()
        if context:
            component_id, component_type = context
            # Add context to data if it's a dict
            if isinstance(data, dict):
                data = data.copy()
                data.setdefault('component_id', component_id)
                data.setdefault('component_type', component_type)
        
        # Create and return typed payload
        return PayloadRegistry.create_payload(event, data)

    def emit_sync(self, event: str, data: Any = None) -> Any:
        """Synchronous emit with typed payload"""
        payload = self._create_typed_payload(event, data)
        
        # 1. Fire events (sync only)
        for listener in self._events[event]:
            if not inspect.iscoroutinefunction(listener):
                self._execute_listener(listener, payload, event, "event")

        # 2. Run hooks (sync only)
        for hook in self._hooks[event]:
            if not inspect.iscoroutinefunction(hook):
                self._execute_listener(hook, payload, event, "hook")

        # 3. Chain pipes (sync only)
        current_payload = payload
        for pipe in self._pipes[event]:
            if not inspect.iscoroutinefunction(pipe):
                result = self._execute_listener(pipe, current_payload, event, "pipe")
                if result is not None:
                    current_payload = result

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

# Global emit function
def emit(event: str, data: Any = None) -> Any:
    """Emit an event through the global event manager"""
    return get_global_event_manager().emit_sync(event, data)

def register_hook(event: str, script_path: str, function_name: str) -> None:
    """Register a hook globally"""
    get_global_event_manager().register_hook_from_config(event, script_path, function_name)

def register_pipe(event: str, script_path: str, function_name: str) -> None:
    """Register a pipe globally"""
    get_global_event_manager().register_pipe_from_config(event, script_path, function_name)

# Convenience factory
def create_default_emitter() -> EventManager:
    return EventManager()