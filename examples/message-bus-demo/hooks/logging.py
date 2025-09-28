"""
Example hooks for message bus demo

These hooks demonstrate that the existing hook system works seamlessly
with the new distributed message bus routing.
"""

import json
import time
import logging

log = logging.getLogger(__name__)


def log_response(payload):
    """Log LLM responses for debugging and monitoring"""
    
    try:
        # Extract response data from payload
        if isinstance(payload, dict):
            response = payload.get('data', payload)
        else:
            response = payload
        
        # Create log entry with timestamp
        log_entry = {
            "timestamp": time.time(),
            "event": "llm_response_generated", 
            "response_preview": str(response)[:100] + "..." if len(str(response)) > 100 else str(response),
            "response_length": len(str(response)),
            "component": "agent"
        }
        
        # Log to file and console
        log.info(f"[Hook] LLM Response: {json.dumps(log_entry, indent=2)}")
        
        # You could also send to external monitoring systems here
        # send_to_monitoring_system(log_entry)
        
    except Exception as e:
        log.error(f"[Hook] Error in log_response hook: {e}")


def monitor_message_bus_routing(payload):
    """Monitor message bus routing events"""
    
    try:
        log.info(f"[Hook] Message bus routing event: {payload}")
        
        # Extract routing information  
        if isinstance(payload, dict):
            source = payload.get('source_component', 'unknown')
            targets = payload.get('targets', [])
            event_type = payload.get('event_type', 'unknown')
            
            routing_info = {
                "source": source,
                "targets": targets, 
                "event": event_type,
                "routing_time": time.time()
            }
            
            log.info(f"[Hook] Routing: {source} -> {targets} ({event_type})")
        
    except Exception as e:
        log.error(f"[Hook] Error in monitor_message_bus_routing hook: {e}")


def debug_component_communication(payload):
    """Debug component-to-component communication"""
    
    try:
        if isinstance(payload, dict):
            component_id = payload.get('component_id', 'unknown')
            component_type = payload.get('component_type', 'unknown')
            event_type = payload.get('event_type', 'unknown')
            
            log.debug(f"[Hook] Component communication: {component_id} ({component_type}) -> {event_type}")
            
            # Log payload structure for debugging
            log.debug(f"[Hook] Payload keys: {list(payload.keys())}")
        
    except Exception as e:
        log.error(f"[Hook] Error in debug_component_communication hook: {e}")


def performance_monitoring(payload):
    """Monitor performance of distributed message routing"""
    
    try:
        start_time = time.time()
        
        # This hook runs after message bus routing
        # You can measure end-to-end latency here
        
        if isinstance(payload, dict):
            routed_at = payload.get('routed_at')
            if routed_at:
                latency_ms = (start_time - routed_at) * 1000
                log.info(f"[Hook] Message bus latency: {latency_ms:.2f}ms")
        
        # Record performance metrics
        performance_data = {
            "hook_execution_time": time.time() - start_time,
            "timestamp": start_time,
            "payload_size": len(str(payload))
        }
        
        log.debug(f"[Hook] Performance: {performance_data}")
        
    except Exception as e:
        log.error(f"[Hook] Error in performance_monitoring hook: {e}")