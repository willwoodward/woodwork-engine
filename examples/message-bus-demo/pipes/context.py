"""
Example pipes for message bus demo

These pipes demonstrate that the existing pipe system works seamlessly
with the new distributed message bus, applying transformations to messages
received from other components.
"""

import time
import json
import logging
from typing import Any, Dict

log = logging.getLogger(__name__)


def add_context(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Add contextual information to incoming messages"""
    
    try:
        # Ensure we have a dict to work with
        if not isinstance(payload, dict):
            payload = {"data": payload}
        
        # Add context information
        enhanced_payload = {
            **payload,
            "context": {
                "processed_at": time.time(),
                "processing_component": "agent",
                "message_bus_routing": True,
                "pipeline_stage": "input_processing"
            }
        }
        
        log.debug(f"[Pipe] Added context to payload: {enhanced_payload.get('context')}")
        
        return enhanced_payload
        
    except Exception as e:
        log.error(f"[Pipe] Error in add_context pipe: {e}")
        return payload  # Return original on error


def format_for_llm(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Format incoming data for LLM processing"""
    
    try:
        if not isinstance(payload, dict):
            payload = {"data": payload}
        
        # Extract the actual input data
        input_data = payload.get('data', payload)
        
        # Format for LLM with system context
        formatted_payload = {
            **payload,
            "formatted_input": f"""
System: You are receiving input via Woodwork's distributed message bus system.

User Input: {input_data}

Context: This message was routed automatically from the input component to you.
Please provide a helpful response that will be automatically routed to the output components.
""",
            "formatting_info": {
                "formatted_at": time.time(),
                "original_input": str(input_data),
                "formatter": "format_for_llm_pipe"
            }
        }
        
        log.debug(f"[Pipe] Formatted input for LLM processing")
        
        return formatted_payload
        
    except Exception as e:
        log.error(f"[Pipe] Error in format_for_llm pipe: {e}")
        return payload


def add_session_info(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Add session information for multi-tenant support"""
    
    try:
        if not isinstance(payload, dict):
            payload = {"data": payload}
        
        # Add session information
        session_info = {
            "session_id": payload.get('session_id', 'default-session'),
            "user_id": payload.get('user_id', 'anonymous'),
            "session_start": time.time(),
            "message_count": 1  # In real implementation, would track this
        }
        
        enhanced_payload = {
            **payload,
            "session_info": session_info
        }
        
        log.debug(f"[Pipe] Added session info: {session_info}")
        
        return enhanced_payload
        
    except Exception as e:
        log.error(f"[Pipe] Error in add_session_info pipe: {e}")
        return payload


def validate_message_format(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize message format from message bus"""
    
    try:
        if not isinstance(payload, dict):
            payload = {"data": payload}
        
        # Ensure required fields exist
        required_fields = ['data']
        for field in required_fields:
            if field not in payload:
                log.warning(f"[Pipe] Missing required field '{field}', adding default")
                payload[field] = None
        
        # Add validation metadata
        validation_info = {
            "validated_at": time.time(),
            "validator": "validate_message_format_pipe",
            "valid": True,
            "field_count": len(payload)
        }
        
        validated_payload = {
            **payload,
            "validation": validation_info
        }
        
        log.debug(f"[Pipe] Validated message format: {validation_info}")
        
        return validated_payload
        
    except Exception as e:
        log.error(f"[Pipe] Error in validate_message_format pipe: {e}")
        # Return payload with error information
        return {
            **payload if isinstance(payload, dict) else {"data": payload},
            "validation": {
                "validated_at": time.time(),
                "validator": "validate_message_format_pipe", 
                "valid": False,
                "error": str(e)
            }
        }


def enrich_with_metadata(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Enrich message with comprehensive metadata for debugging"""
    
    try:
        if not isinstance(payload, dict):
            payload = {"data": payload}
        
        # Add comprehensive metadata
        metadata = {
            "message_bus": {
                "routing_enabled": True,
                "distributed_processing": True,
                "component_communication": True
            },
            "processing": {
                "pipe_name": "enrich_with_metadata", 
                "processed_at": time.time(),
                "payload_size_bytes": len(json.dumps(payload, default=str)),
                "field_count": len(payload)
            },
            "system": {
                "woodwork_version": "2.0.0-message-bus",
                "feature": "distributed_component_communication"
            }
        }
        
        enriched_payload = {
            **payload,
            "metadata": metadata
        }
        
        log.debug(f"[Pipe] Enriched with metadata: {len(metadata)} fields added")
        
        return enriched_payload
        
    except Exception as e:
        log.error(f"[Pipe] Error in enrich_with_metadata pipe: {e}")
        return payload