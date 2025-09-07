import os
import sys
import importlib.util
import logging
from typing import List, Optional, Any, Dict
from woodwork.types.workflows import Hook, Pipe
from woodwork.events import EventEmitter, create_default_emitter

log = logging.getLogger(__name__)


class component:
    def __init__(self, name, component, type, **config):
        self.name = name
        self.component = component
        self.type = type
        self.config = config
        self._emitter: Optional[EventEmitter] = None
        self._hooks: List[Hook] = []
        self._pipes: List[Pipe] = []
        
        self._setup_event_system(config)
    
    def _setup_event_system(self, config: Dict[str, Any]):
        """Initialize the event system with hooks and pipes from config."""
        try:
            # Check if hooks are configured
            hooks_config = config.get("hooks", [])
            if hooks_config:
                self._hooks = self._parse_hooks_config(hooks_config)
            
            # Check if pipes are configured  
            pipes_config = config.get("pipes", [])
            if pipes_config:
                self._pipes = self._parse_pipes_config(pipes_config)
            
            # Create EventEmitter if we have hooks or pipes
            if self._hooks or self._pipes:
                self._emitter = config.get("events") or create_default_emitter()
                self._register_hooks()
                self._register_pipes()
                
        except Exception as e:
            log.warning(f"Failed to setup event system for component {self.name}: {e}")
    
    def _parse_hooks_config(self, hooks_config: List[Dict[str, Any]]) -> List[Hook]:
        """Parse hook configurations from config."""
        hooks = []
        for hook_config in hooks_config:
            try:
                hook = Hook.from_dict(hook_config)
                hooks.append(hook)
            except Exception as e:
                log.warning(f"Invalid hook config in component {self.name}: {e}")
        return hooks
    
    def _parse_pipes_config(self, pipes_config: List[Dict[str, Any]]) -> List[Pipe]:
        """Parse pipe configurations from config."""
        pipes = []
        for pipe_config in pipes_config:
            try:
                pipe = Pipe.from_dict(pipe_config)
                pipes.append(pipe)
            except Exception as e:
                log.warning(f"Invalid pipe config in component {self.name}: {e}")
        return pipes
    
    def _register_hooks(self):
        """Register all configured hooks with the EventEmitter."""
        if not self._emitter:
            return
            
        for hook in self._hooks:
            try:
                func = self._load_function(hook.script_path, hook.function_name)
                if func:
                    self._emitter.on(hook.event, func)
                    log.debug(f"Registered hook for event '{hook.event}' from {hook.script_path}::{hook.function_name}")
            except Exception as e:
                log.warning(f"Failed to register hook {hook.function_name} for event {hook.event}: {e}")
    
    def _register_pipes(self):
        """Register all configured pipes with the EventEmitter."""
        if not self._emitter:
            return
            
        for pipe in self._pipes:
            try:
                func = self._load_function(pipe.script_path, pipe.function_name)
                if func:
                    self._emitter.add_pipe(pipe.event, func)
                    log.debug(f"Registered pipe for event '{pipe.event}' from {pipe.script_path}::{pipe.function_name}")
            except Exception as e:
                log.warning(f"Failed to register pipe {pipe.function_name} for event {pipe.event}: {e}")
    
    def _load_function(self, script_path: str, function_name: str):
        """Load a function from a Python script file."""
        try:
            # Handle relative paths relative to the component's location
            if not os.path.isabs(script_path):
                # Try relative to current working directory first
                if os.path.exists(script_path):
                    abs_path = os.path.abspath(script_path)
                else:
                    # Try relative to the examples directory if in examples
                    if 'examples' in os.getcwd():
                        abs_path = os.path.join(os.getcwd(), script_path)
                    else:
                        abs_path = script_path
            else:
                abs_path = script_path
            
            if not os.path.exists(abs_path):
                log.warning(f"Script file not found: {abs_path}")
                return None
            
            # Load the module
            spec = importlib.util.spec_from_file_location("dynamic_module", abs_path)
            if spec is None or spec.loader is None:
                log.warning(f"Could not load module spec from {abs_path}")
                return None
                
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Get the function
            if hasattr(module, function_name):
                return getattr(module, function_name)
            else:
                log.warning(f"Function {function_name} not found in {abs_path}")
                return None
                
        except Exception as e:
            log.error(f"Error loading function {function_name} from {script_path}: {e}")
            return None
    
    @property
    def emitter(self) -> Optional[EventEmitter]:
        """Get the EventEmitter instance for this component."""
        return self._emitter
