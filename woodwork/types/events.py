"""
Event payload type system for Woodwork engine.

This module provides typed, validated event payloads designed for JSON 
serialization/deserialization over HTTP. Payloads include component 
attribution for namespacing without event name prefixing.
"""

import time
import json
from typing import Any, Dict, Optional, Type, Union, List
from dataclasses import dataclass, field, asdict, fields, MISSING
from datetime import datetime
import logging

log = logging.getLogger(__name__)


@dataclass
class BasePayload:
    """Base class for all event payloads with JSON serialization support"""
    timestamp: float = field(default_factory=time.time)
    component_id: Optional[str] = None
    component_type: Optional[str] = None
    
    def to_json(self) -> str:
        """Serialize payload to JSON string"""
        return json.dumps(asdict(self), default=str)
    
    @classmethod
    def from_json(cls, json_str: str) -> "BasePayload":
        """Create payload from JSON string"""
        try:
            data = json.loads(json_str)
            return cls.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            log.error(f"Failed to parse JSON for {cls.__name__}: {e}")
            raise ValueError(f"Invalid JSON for {cls.__name__}: {e}")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BasePayload":
        """Create payload from dictionary (for HTTP JSON payloads)"""
        # Extract fields that match the dataclass
        field_names = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in field_names}
        
        # Set timestamp if not provided
        if 'timestamp' not in filtered_data:
            filtered_data['timestamp'] = time.time()
            
        try:
            return cls(**filtered_data)
        except TypeError as e:
            log.error(f"Failed to create {cls.__name__} from dict: {e}")
            raise ValueError(f"Invalid data for {cls.__name__}: {e}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
    
    def validate(self) -> List[str]:
        """Validate payload and return list of error messages"""
        errors = []
        # Override in subclasses for specific validation
        return errors
    
    def is_valid(self) -> bool:
        """Check if payload is valid"""
        return len(self.validate()) == 0


@dataclass
class GenericPayload(BasePayload):
    """Generic payload that accepts any additional data"""
    data: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GenericPayload":
        """Create GenericPayload, storing unknown fields in data"""
        # Extract known base fields
        base_data = {}
        extra_data = {}
        
        base_field_names = {f.name for f in fields(BasePayload)}
        
        for k, v in data.items():
            if k in base_field_names or k == 'data':
                base_data[k] = v
            else:
                extra_data[k] = v
        
        # Set timestamp if not provided
        if 'timestamp' not in base_data:
            base_data['timestamp'] = time.time()
            
        # Merge extra_data into existing data field if present
        existing_data = base_data.get('data', {})
        if isinstance(existing_data, dict):
            existing_data.update(extra_data)
            base_data['data'] = existing_data
        else:
            base_data['data'] = extra_data
            
        return cls(**base_data)


@dataclass  
class InputReceivedPayload(BasePayload):
    """Payload for input.received events"""
    input: str = ""
    inputs: Dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None
    
    def validate(self) -> List[str]:
        """Validate input payload"""
        errors = []
        if not self.input or not self.input.strip():
            errors.append("input field cannot be empty")
        if not isinstance(self.inputs, dict):
            errors.append("inputs field must be a dictionary")
        return errors


@dataclass
class AgentThoughtPayload(BasePayload):
    """Payload for agent.thought events"""
    thought: str = ""
    
    def validate(self) -> List[str]:
        """Validate thought payload"""
        errors = []
        if not self.thought or not self.thought.strip():
            errors.append("thought field cannot be empty")
        return errors


@dataclass
class AgentActionPayload(BasePayload):
    """Payload for agent.action events"""
    action: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> List[str]:
        """Validate action payload"""
        errors = []
        if not self.action:
            errors.append("action field cannot be empty")
        elif not isinstance(self.action, dict):
            errors.append("action field must be a dictionary")
        return errors


@dataclass
class ToolCallPayload(BasePayload):
    """Payload for tool.call events"""
    tool: str = ""
    args: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> List[str]:
        """Validate tool call payload"""
        errors = []
        if not self.tool or not self.tool.strip():
            errors.append("tool field cannot be empty")
        if not isinstance(self.args, dict):
            errors.append("args field must be a dictionary")
        return errors


@dataclass
class ToolObservationPayload(BasePayload):
    """Payload for tool.observation events"""
    tool: str = ""
    observation: str = ""
    
    def validate(self) -> List[str]:
        """Validate tool observation payload"""
        errors = []
        if not self.tool or not self.tool.strip():
            errors.append("tool field cannot be empty")
        if not isinstance(self.observation, str):
            errors.append("observation field must be a string")
        return errors


@dataclass
class AgentStepCompletePayload(BasePayload):
    """Payload for agent.step_complete events"""
    step: int = 0
    session_id: Optional[str] = None
    
    def validate(self) -> List[str]:
        """Validate step complete payload"""
        errors = []
        if not isinstance(self.step, int) or self.step < 0:
            errors.append("step field must be a non-negative integer")
        return errors


@dataclass  
class AgentErrorPayload(BasePayload):
    """Payload for agent.error events"""
    error: str = ""
    error_type: str = "Unknown"
    context: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> List[str]:
        """Validate error payload"""
        errors = []
        if not self.error or not self.error.strip():
            errors.append("error field cannot be empty")
        if not isinstance(self.context, dict):
            errors.append("context field must be a dictionary")
        return errors
    
    @classmethod
    def from_exception(cls, exc: Exception, context: Optional[Dict[str, Any]] = None, **kwargs) -> "AgentErrorPayload":
        """Create AgentErrorPayload from an exception"""
        return cls(
            error=str(exc),
            error_type=exc.__class__.__name__,
            context=context or {},
            **kwargs
        )


class PayloadRegistry:
    """Registry mapping event names to payload types with JSON validation"""
    
    _registry: Dict[str, Type[BasePayload]] = {
        "input.received": InputReceivedPayload,
        "agent.thought": AgentThoughtPayload,
        "agent.action": AgentActionPayload,
        "tool.call": ToolCallPayload,
        "tool.observation": ToolObservationPayload,
        "agent.step_complete": AgentStepCompletePayload,
        "agent.error": AgentErrorPayload,
    }
    
    @classmethod
    def get_payload_type(cls, event: str) -> Type[BasePayload]:
        """Get the payload type for an event, defaulting to GenericPayload"""
        return cls._registry.get(event, GenericPayload)
    
    @classmethod
    def register(cls, event: str, payload_type: Type[BasePayload]):
        """Register a custom payload type for an event"""
        if not issubclass(payload_type, BasePayload):
            raise ValueError(f"Payload type must inherit from BasePayload")
        cls._registry[event] = payload_type
        log.debug(f"Registered payload type {payload_type.__name__} for event '{event}'")
    
    @classmethod
    def create_payload(cls, event: str, data: Union[Dict[str, Any], BasePayload, str]) -> BasePayload:
        """Create a typed payload from various input formats with validation"""
        if isinstance(data, BasePayload):
            return data
            
        if data is None:
            data = {}
            
        payload_type = cls.get_payload_type(event)
        
        try:
            if isinstance(data, str):
                # Assume it's JSON
                payload = payload_type.from_json(data)
            elif isinstance(data, dict):
                payload = payload_type.from_dict(data)
            else:
                log.warning(f"Unexpected data type for event '{event}': {type(data)}")
                return GenericPayload.from_dict({"data": data})
                
            # Validate the created payload
            validation_errors = payload.validate()
            if validation_errors:
                log.warning(f"Validation errors for event '{event}': {validation_errors}")
                # Return payload anyway but log the errors
                
            return payload
            
        except Exception as e:
            log.warning(f"Failed to create {payload_type.__name__} for event '{event}': {e}. Falling back to GenericPayload")
            # Fallback to GenericPayload for compatibility
            fallback_data = data if isinstance(data, dict) else {"raw_data": data}
            return GenericPayload.from_dict(fallback_data)
    
    @classmethod
    def validate_event_data(cls, event: str, data: Union[Dict[str, Any], str]) -> List[str]:
        """Validate event data without creating payload"""
        payload_type = cls.get_payload_type(event)
        try:
            if isinstance(data, str):
                payload = payload_type.from_json(data)
            else:
                payload = payload_type.from_dict(data)
            return payload.validate()
        except Exception as e:
            return [f"Failed to parse data: {e}"]
    
    @classmethod
    def get_event_schema(cls, event: str) -> Dict[str, Any]:
        """Get JSON schema information for an event type"""
        payload_type = cls.get_payload_type(event)
        schema = {
            "event": event,
            "payload_type": payload_type.__name__,
            "fields": {}
        }
        
        for field_info in fields(payload_type):
            schema["fields"][field_info.name] = {
                "type": str(field_info.type),
                "required": field_info.default == MISSING and field_info.default_factory == MISSING
            }
            
        return schema