"""
Event source tracking system for component attribution.

Provides thread-local component tracking that allows events to be automatically
attributed to the component that emitted them without requiring explicit
prefixing of event names.

This is different from AI Agent "context" which refers to conversation history,
memory, and session state.
"""

from contextvars import ContextVar
from typing import Optional, Tuple
import logging

log = logging.getLogger(__name__)

# Thread-local tracking for current component
_current_component: ContextVar[Optional[Tuple[str, str]]] = ContextVar('current_component')


class EventSource:
    """Manages component tracking for event attribution"""
    
    @staticmethod
    def set_current(component_id: str, component_type: str):
        """Set current component for event attribution"""
        _current_component.set((component_id, component_type))
        log.debug(f"Set event source: {component_id} ({component_type})")
    
    @staticmethod
    def get_current() -> Optional[Tuple[str, str]]:
        """Get current component info for event attribution"""
        try:
            return _current_component.get()
        except LookupError:
            # ContextVar not set in this context
            return None
    
    @staticmethod
    def clear():
        """Clear component tracking"""
        _current_component.set(None)
        log.debug("Cleared event source")
    
    @classmethod
    def track_component(cls, component_id: str, component_type: str):
        """Context manager for temporary component tracking"""
        class _ComponentTracker:
            def __init__(self, comp_id: str, comp_type: str):
                self.component_id = comp_id
                self.component_type = comp_type
                self.previous = None
            
            def __enter__(self):
                self.previous = cls.get_current()
                cls.set_current(self.component_id, self.component_type)
                return self
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                if self.previous:
                    cls.set_current(*self.previous)
                else:
                    cls.clear()
        
        return _ComponentTracker(component_id, component_type)


def track_events_from(component_id: str, component_type: str):
    """Decorator to track events from a specific component"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with EventSource.track_component(component_id, component_type):
                return func(*args, **kwargs)
        return wrapper
    return decorator