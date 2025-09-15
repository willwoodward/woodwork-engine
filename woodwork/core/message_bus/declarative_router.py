"""
Declarative Router for Component 'to:' Property Routing

This module implements the core routing logic that reads .ww component configurations
and automatically routes messages based on the declarative 'to:' property, replacing
the centralized Task Master orchestration with distributed routing.
"""

import asyncio
import logging
import time
from typing import Dict, List, Any, Optional, Set, Union

from .interface import MessageBusInterface, MessageEnvelope, create_component_message, create_hook_message

log = logging.getLogger(__name__)


class DeclarativeRouter:
    """
    Routes component outputs based on declarative 'to:' configuration
    
    This class replaces the Task Master's centralized orchestration by reading
    component configurations and automatically routing messages when components
    emit events, preserving the declarative nature users expect.
    """
    
    def __init__(self, message_bus: MessageBusInterface):
        self.message_bus = message_bus
        
        # Routing configuration
        self.routing_table: Dict[str, List[str]] = {}
        self.component_configs: Dict[str, Dict[str, Any]] = {}
        
        # Workflow inference
        self.inferred_workflows: Dict[str, List[str]] = {}
        
        # Statistics
        self.stats = {
            "messages_routed": 0,
            "routing_failures": 0,
            "components_registered": 0,
            "active_routes": 0
        }
        
        log.debug("[DeclarativeRouter] Initialized with message bus")
    
    def configure_from_components(self, component_configs: Dict[str, Dict[str, Any]]) -> None:
        """
        Build routing table from .ww component configurations
        
        Args:
            component_configs: Dict of component_name -> config from parser
        """
        
        log.info("[DeclarativeRouter] Configuring routing from %d components", len(component_configs))
        
        self.component_configs = component_configs
        self.routing_table.clear()
        
        # Build explicit routing table from 'to:' properties
        for component_name, config in component_configs.items():
            targets = self._extract_targets(config.get('to'))
            
            if targets:
                self.routing_table[component_name] = targets
                log.debug("[DeclarativeRouter] Component '%s' routes to: %s", component_name, targets)
            else:
                self.routing_table[component_name] = []
                log.debug("[DeclarativeRouter] Component '%s' has no routing targets", component_name)
        
        # Infer workflow chains for components without explicit 'to:' configuration
        self._infer_workflow_chains()
        
        # Update statistics
        self.stats["components_registered"] = len(component_configs)
        self.stats["active_routes"] = sum(len(targets) for targets in self.routing_table.values())
        
        log.info("[DeclarativeRouter] Routing configured: %d components, %d total routes", 
                 self.stats["components_registered"], self.stats["active_routes"])
    
    def _extract_targets(self, to_config: Any) -> List[str]:
        """Extract routing targets from 'to:' configuration"""
        if not to_config:
            return []
        
        if isinstance(to_config, str):
            return [to_config]
        elif isinstance(to_config, list):
            return [str(target) for target in to_config]
        elif hasattr(to_config, 'name'):
            # Handle component object that was resolved by parser
            log.debug("[DeclarativeRouter] Converting component object to name: %s", to_config.name)
            return [to_config.name]
        else:
            # Try to convert to string as fallback
            target_str = str(to_config)
            if target_str and not target_str.startswith('<'):
                log.debug("[DeclarativeRouter] Converting to string: %s", target_str)
                return [target_str]
            else:
                log.warning("[DeclarativeRouter] Invalid 'to:' configuration type: %s", type(to_config))
                return []
    
    def _infer_workflow_chains(self) -> None:
        """
        Infer workflow chains for components that don't have explicit 'to:' configuration
        
        This provides intelligent defaults for common patterns like input -> agent -> output
        """
        
        log.debug("[DeclarativeRouter] Inferring workflow chains")
        
        # Get component types
        component_types = {
            name: config.get('component', 'unknown')
            for name, config in self.component_configs.items()
        }
        
        log.debug("[DeclarativeRouter] Component types detected: %s", component_types)
        
        # Find common component patterns
        inputs = [name for name, comp_type in component_types.items() if comp_type == 'inputs']
        agents = [name for name, comp_type in component_types.items() if comp_type in ['llms', 'agents']]
        outputs = [name for name, comp_type in component_types.items() if comp_type == 'outputs']
        
        log.debug("[DeclarativeRouter] Found components - inputs: %s, agents: %s, outputs: %s", 
                  inputs, agents, outputs)
        
        # Infer input -> agent routing if not explicitly configured
        for input_comp in inputs:
            if not self.routing_table.get(input_comp):
                if agents:
                    # Route first input to first agent (simple case)
                    target_agent = agents[0] if len(inputs) == 1 else None
                    if target_agent:
                        self.routing_table[input_comp] = [target_agent]
                        log.debug("[DeclarativeRouter] Inferred routing: %s -> %s", input_comp, target_agent)
        
        # Infer agent -> output routing if not explicitly configured  
        for agent_comp in agents:
            if not self.routing_table.get(agent_comp):
                if outputs:
                    # Route agent to all outputs (broadcast pattern)
                    self.routing_table[agent_comp] = outputs
                    log.debug("[DeclarativeRouter] Inferred routing: %s -> %s", agent_comp, outputs)
                else:
                    # No explicit output components - route to console
                    self.routing_table[agent_comp] = ["_console_output"]
                    log.debug("[DeclarativeRouter] Inferred routing: %s -> console output", agent_comp)
        
        # Update statistics
        self.stats["active_routes"] = sum(len(targets) for targets in self.routing_table.values())
        
        log.info("[DeclarativeRouter] Workflow inference complete: %d total routes", 
                 self.stats["active_routes"])
    
    async def route_component_output(
        self, 
        source_component: str, 
        event_type: str, 
        data: Any, 
        session_id: str
    ) -> bool:
        """
        Route component output to configured targets
        
        This is the main routing function called when components emit events.
        It replaces the Task Master's centralized orchestration.
        
        Args:
            source_component: Name of component emitting the event
            event_type: Type of event being emitted
            data: Event data/payload
            session_id: Session identifier for isolation
            
        Returns:
            True if routing succeeded to all targets
        """
        
        start_time = time.time()
        
        # Get routing targets for this component
        targets = self.routing_table.get(source_component, [])
        
        if not targets:
            log.debug("[DeclarativeRouter] No routing targets for component '%s', event '%s'", 
                      source_component, event_type)
            return True  # No targets is not a failure
        
        log.debug("[DeclarativeRouter] Routing '%s' from %s to %d targets: %s (session: %s)", 
                  event_type, source_component, len(targets), targets, session_id)
        
        success_count = 0
        failure_count = 0
        
        # Route to each target component
        for target_component in targets:
            try:
                # Create message envelope for component-to-component communication
                envelope = create_component_message(
                    session_id=session_id,
                    event_type=event_type,
                    payload={
                        "data": data,
                        "source_component": source_component,
                        "routed_at": time.time()
                    },
                    target_component=target_component,
                    sender_component=source_component
                )
                
                # Send via message bus
                success = await self.message_bus.send_to_component(envelope)
                
                if success:
                    success_count += 1
                    log.debug("[DeclarativeRouter] Successfully routed %s -> %s", 
                              source_component, target_component)
                else:
                    failure_count += 1
                    log.warning("[DeclarativeRouter] Failed to route %s -> %s", 
                               source_component, target_component)
                
            except Exception as e:
                failure_count += 1
                log.error("[DeclarativeRouter] Error routing %s -> %s: %s", 
                          source_component, target_component, e)
        
        # Update statistics
        self.stats["messages_routed"] += success_count
        self.stats["routing_failures"] += failure_count
        
        routing_time_ms = (time.time() - start_time) * 1000
        
        log.debug("[DeclarativeRouter] Routing complete for %s: %d success, %d failed in %.2fms", 
                  source_component, success_count, failure_count, routing_time_ms)
        
        return failure_count == 0
    
    async def broadcast_hook_event(
        self, 
        source_component: str, 
        event_type: str, 
        data: Any, 
        session_id: str
    ) -> bool:
        """
        Broadcast event to all hook subscribers (pub/sub pattern)
        
        This handles hook broadcasting separately from component routing,
        maintaining the existing hook behavior while adding distributed capabilities.
        
        Args:
            source_component: Name of component emitting the event
            event_type: Type of event being emitted  
            data: Event data/payload
            session_id: Session identifier for isolation
            
        Returns:
            True if broadcast succeeded
        """
        
        log.debug("[DeclarativeRouter] Broadcasting hook event '%s' from %s (session: %s)", 
                  event_type, source_component, session_id)
        
        try:
            # Create hook message envelope for pub/sub
            envelope = create_hook_message(
                session_id=session_id,
                event_type=event_type,
                payload={
                    "data": data,
                    "source_component": source_component,
                    "broadcast_at": time.time()
                },
                sender_component=source_component
            )
            
            # Broadcast via message bus pub/sub
            success = await self.message_bus.publish(envelope)
            
            if success:
                log.debug("[DeclarativeRouter] Hook broadcast successful for '%s'", event_type)
            else:
                log.warning("[DeclarativeRouter] Hook broadcast failed for '%s'", event_type)
                self.stats["routing_failures"] += 1
            
            return success
            
        except Exception as e:
            log.error("[DeclarativeRouter] Error broadcasting hook event '%s': %s", event_type, e)
            self.stats["routing_failures"] += 1
            return False
    
    def get_routing_targets(self, component_name: str) -> List[str]:
        """Get routing targets for a specific component"""
        return self.routing_table.get(component_name, []).copy()
    
    def has_routing_targets(self, component_name: str) -> bool:
        """Check if component has any routing targets"""
        return bool(self.routing_table.get(component_name))
    
    def add_routing_target(self, component_name: str, target: str) -> None:
        """Dynamically add routing target to component"""
        if component_name not in self.routing_table:
            self.routing_table[component_name] = []
        
        if target not in self.routing_table[component_name]:
            self.routing_table[component_name].append(target)
            self.stats["active_routes"] += 1
            
            log.debug("[DeclarativeRouter] Added routing: %s -> %s", component_name, target)
    
    def remove_routing_target(self, component_name: str, target: str) -> bool:
        """Dynamically remove routing target from component"""
        if component_name in self.routing_table and target in self.routing_table[component_name]:
            self.routing_table[component_name].remove(target)
            self.stats["active_routes"] -= 1
            
            log.debug("[DeclarativeRouter] Removed routing: %s -> %s", component_name, target)
            return True
        
        return False
    
    def get_workflow_chains(self) -> Dict[str, List[str]]:
        """Get inferred workflow chains"""
        return self.inferred_workflows.copy()
    
    def get_routing_stats(self) -> Dict[str, Any]:
        """Get comprehensive routing statistics"""
        return {
            **self.stats,
            "routing_table_size": len(self.routing_table),
            "total_configured_components": len(self.component_configs),
            "average_targets_per_component": (
                self.stats["active_routes"] / max(len(self.routing_table), 1)
            ),
            "routing_table": {
                component: targets for component, targets in self.routing_table.items()
            }
        }
    
    def get_component_workflow_info(self, component_name: str) -> Dict[str, Any]:
        """Get workflow information for a specific component"""
        targets = self.routing_table.get(component_name, [])
        config = self.component_configs.get(component_name, {})
        
        return {
            "component_name": component_name,
            "component_type": config.get('component', 'unknown'),
            "routing_targets": targets,
            "has_explicit_routing": 'to' in config,
            "routing_count": len(targets),
            "is_workflow_end": len(targets) == 0,
            "config": config
        }
    
    def validate_routing_configuration(self) -> Dict[str, Any]:
        """Validate routing configuration and identify potential issues"""
        issues = []
        warnings = []
        
        # Check for orphaned components (no inputs, no outputs)
        orphaned = []
        for component_name in self.component_configs:
            has_inputs = any(component_name in targets for targets in self.routing_table.values())
            has_outputs = bool(self.routing_table.get(component_name))
            
            if not has_inputs and not has_outputs:
                orphaned.append(component_name)
        
        if orphaned:
            warnings.append(f"Orphaned components (no inputs or outputs): {orphaned}")
        
        # Check for circular routing
        def has_cycle(component: str, visited: Set[str], path: List[str]) -> bool:
            if component in visited:
                cycle_start = path[path.index(component):]
                issues.append(f"Circular routing detected: {' -> '.join(cycle_start + [component])}")
                return True
            
            visited.add(component)
            path.append(component)
            
            for target in self.routing_table.get(component, []):
                if has_cycle(target, visited.copy(), path.copy()):
                    return True
            
            return False
        
        for component in self.routing_table:
            has_cycle(component, set(), [])
        
        # Check for unreachable targets
        all_components = set(self.component_configs.keys())
        
        # Add built-in virtual components that we create automatically
        built_in_components = {"_console_output"}
        all_valid_targets = all_components | built_in_components
        
        referenced_targets = set()
        for targets in self.routing_table.values():
            referenced_targets.update(targets)
        
        unreachable = referenced_targets - all_valid_targets
        if unreachable:
            issues.append(f"Routing targets not found in configuration: {list(unreachable)}")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "stats": {
                "total_components": len(all_components),
                "routed_components": len([c for c in self.routing_table if self.routing_table[c]]),
                "orphaned_components": len(orphaned),
                "total_routes": sum(len(targets) for targets in self.routing_table.values())
            }
        }