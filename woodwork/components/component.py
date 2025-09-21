import os
import sys
import importlib.util
import logging
import asyncio
from typing import List, Optional, Any, Dict
from woodwork.types.workflows import Hook, Pipe
from woodwork.events import EventManager, create_default_emitter, get_global_event_manager
from woodwork.components.streaming_mixin import StreamingMixin
from woodwork.core.stream_manager import StreamManager
from woodwork.core.message_bus.integration import MessageBusIntegration, register_component_with_message_bus

log = logging.getLogger(__name__)


class component(StreamingMixin, MessageBusIntegration):
    def __init__(self, name, component, type, **config):
        log.debug("[component] Initializing component '%s' (type: %s, component: %s) with config keys: %s", 
                  name, type, component, list(config.keys()))
        
        # Set basic attributes first
        self.name = name
        self.component = component
        self.type = type
        self.config = config
        
        # Initialize both mixins with the full config
        log.debug("[component] Calling super().__init__ for '%s'", name)
        super().__init__(name=name, config=config)
        
        log.debug("[component] Component '%s' initialization complete, hasattr(output_targets): %s", 
                  name, hasattr(self, 'output_targets'))
        
        self._emitter: Optional[EventManager] = None
        self._hooks: List[Hook] = []
        self._pipes: List[Pipe] = []
        
        self._setup_event_system(config)
        
        # Register with global message bus manager
        register_component_with_message_bus(self)

        # Set up tool message handling if this is a tool component
        self._setup_tool_message_handling()
        
        # Log configuration
        if hasattr(self, 'streaming_enabled') and self.streaming_enabled:
            log.debug(f"[Component {self.name}] Streaming enabled: input={self.streaming_input}, output={self.streaming_output}")
        
        if hasattr(self, 'output_targets') and self.output_targets:
            log.debug(f"[Component {self.name}] Message bus routing targets: {self.output_targets}")
        
        streaming_enabled = getattr(self, 'streaming_enabled', False)
        self.streaming_enabled = streaming_enabled

        # Ensure output_targets is properly set from config
        # The parser resolves 'to: [ag]' to actual component objects
        if not hasattr(self, 'output_targets') or self.output_targets is None:
            self.output_targets = config.get("to", [])

        # Ensure it's always a list for consistency
        if self.output_targets and not isinstance(self.output_targets, list):
            self.output_targets = [self.output_targets]

        # Ensure required attributes exist for MessageBusIntegration
        if not hasattr(self, 'session_id'):
            self.session_id = 'default'
        if not hasattr(self, 'integration_stats'):
            self.integration_stats = {
                "messages_sent": 0,
                "messages_received": 0,
                "routing_events": 0,
                "integration_errors": 0
            }
        
        log.info(f"[Component {self.name}] Initialized with streaming={streaming_enabled}, routing={bool(self.output_targets)}, type={self.type}")

    def _setup_tool_message_handling(self):
        """Setup message bus handling for tool components."""
        try:
            # Check if this is a tool component (has tool_interface)
            from woodwork.interfaces.tool_interface import tool_interface
            if isinstance(self, tool_interface):
                log.debug(f"[Component {self.name}] Setting up tool message handling")

                # Register handler for tool.execute messages
                async def handle_tool_execute(payload):
                    if hasattr(self, 'handle_tool_execute_message'):
                        return await self.handle_tool_execute_message(payload)
                    else:
                        log.warning(f"[Tool {self.name}] Received tool.execute message but no handler available")

                # Store the handler for potential message bus registration
                self._tool_message_handler = handle_tool_execute
                log.info(f"[Tool {self.name}] Registered for tool.execute messages via message bus")

        except Exception as e:
            log.debug(f"[Component {self.name}] No tool interface detected: {e}")

    def _setup_event_system(self, config: Dict[str, Any]):
        """Initialize the event system with hooks and pipes from config."""
        try:
            log.debug(f"[Component {self.name}] Setting up event system...")
            log.debug(f"[Component {self.name}] Config keys: {list(config.keys())}")
            
            # Check if hooks are configured
            hooks_config = config.get("hooks", [])
            if hooks_config:
                log.debug(f"[Component {self.name}] Found {len(hooks_config)} hook configurations: {hooks_config}")
                self._hooks = self._parse_hooks_config(hooks_config)
            else:
                log.debug(f"[Component {self.name}] No hooks configured")
            
            # Check if pipes are configured  
            pipes_config = config.get("pipes", [])
            if pipes_config:
                log.debug(f"[Component {self.name}] Found {len(pipes_config)} pipe configurations: {pipes_config}")
                self._pipes = self._parse_pipes_config(pipes_config)
            else:
                log.debug(f"[Component {self.name}] No pipes configured")
            
            # Register hooks and pipes with the global event manager
            if self._hooks or self._pipes:
                log.debug(f"[Component {self.name}] Registering with global event manager: {len(self._hooks)} hooks and {len(self._pipes)} pipes")
                self._register_hooks_global()
                self._register_pipes_global()
            else:
                log.debug(f"[Component {self.name}] No hooks or pipes configured")
                
        except Exception as e:
            log.warning(f"Failed to setup event system for component {self.name}: {e}")
    
    def _parse_hooks_config(self, hooks_config: List[Dict[str, Any]]) -> List[Hook]:
        """Parse hook configurations from config."""
        hooks = []
        log.debug(f"[Component {self.name}] Parsing hooks_config type: {type(hooks_config)}, content: {hooks_config}")
        for i, hook_config in enumerate(hooks_config):
            try:
                log.debug(f"[Component {self.name}] Processing hook {i}: type={type(hook_config)}, content={hook_config}")
                hook = Hook.from_dict(hook_config)
                hooks.append(hook)
            except Exception as e:
                log.warning(f"Invalid hook config in component {self.name}: {e}")
        return hooks
    
    def _parse_pipes_config(self, pipes_config: List[Dict[str, Any]]) -> List[Pipe]:
        """Parse pipe configurations from config."""
        pipes = []
        log.debug(f"[Component {self.name}] Parsing pipes_config type: {type(pipes_config)}, content: {pipes_config}")
        for i, pipe_config in enumerate(pipes_config):
            try:
                log.debug(f"[Component {self.name}] Processing pipe {i}: type={type(pipe_config)}, content={pipe_config}")
                pipe = Pipe.from_dict(pipe_config)
                pipes.append(pipe)
            except Exception as e:
                log.warning(f"Invalid pipe config in component {self.name}: {e}")
        return pipes
    
    def _register_hooks_global(self):
        """Register all configured hooks with both the old EventManager and unified event bus."""
        global_manager = get_global_event_manager()

        # Also register with unified event bus
        from woodwork.core.unified_event_bus import get_global_event_bus
        unified_bus = get_global_event_bus()

        log.debug(f"[Component {self.name}] Registering {len(self._hooks)} hooks globally...")
        for i, hook in enumerate(self._hooks):
            try:
                log.debug(f"[Component {self.name}] Loading hook {i+1}: {hook.function_name} from {hook.script_path} for event '{hook.event}'")
                func = self._load_function(hook.script_path, hook.function_name)
                if func:
                    # Register with old event manager (for backward compatibility)
                    global_manager.on_hook(hook.event, func)
                    # Register with unified event bus (for new system)
                    unified_bus.register_hook(hook.event, func)
                    log.debug(f"[Component {self.name}] Successfully registered hook for event '{hook.event}' from {hook.script_path}::{hook.function_name} (old + unified)")
                else:
                    log.warning(f"[Component {self.name}] Failed to load function {hook.function_name} from {hook.script_path}")
            except Exception as e:
                log.warning(f"[Component {self.name}] Failed to register hook {hook.function_name} for event {hook.event}: {e}")
    
    def _register_pipes_global(self):
        """Register all configured pipes with both the old EventManager and unified event bus."""
        global_manager = get_global_event_manager()

        # Also register with unified event bus
        from woodwork.core.unified_event_bus import get_global_event_bus
        unified_bus = get_global_event_bus()

        log.debug(f"[Component {self.name}] Registering {len(self._pipes)} pipes globally...")
        for i, pipe in enumerate(self._pipes):
            try:
                log.debug(f"[Component {self.name}] Loading pipe {i+1}: {pipe.function_name} from {pipe.script_path} for event '{pipe.event}'")
                func = self._load_function(pipe.script_path, pipe.function_name)
                if func:
                    # Register with old event manager (for backward compatibility)
                    global_manager.on_pipe(pipe.event, func)
                    # Register with unified event bus (for new system)
                    unified_bus.register_pipe(pipe.event, func)
                    log.debug(f"[Component {self.name}] Successfully registered pipe for event '{pipe.event}' from {pipe.script_path}::{pipe.function_name} (old + unified)")
                else:
                    log.warning(f"[Component {self.name}] Failed to load function {pipe.function_name} from {pipe.script_path}")
            except Exception as e:
                log.warning(f"[Component {self.name}] Failed to register pipe {pipe.function_name} for event {pipe.event}: {e}")
    
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
    def emitter(self) -> Optional[EventManager]:
        """Get the EventManager instance for this component."""
        return self._emitter
