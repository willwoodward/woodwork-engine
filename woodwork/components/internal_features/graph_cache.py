"""Graph Cache Feature Implementation with Auto-Component Creation.

This module provides automatic graph caching functionality with auto-created Neo4j components.
"""

import logging
from typing import Dict, List, Tuple, Callable, Any
from woodwork.types.events import AgentActionPayload, AgentStepCompletePayload, InputReceivedPayload
from .base import InternalFeature

log = logging.getLogger(__name__)


class GraphCacheFeature(InternalFeature):
    """Internal feature for automatic graph caching with auto-created Neo4j component."""

    def __init__(self):
        self._neo4j_component = None
        self._component_ref = None
        log.debug("GraphCacheFeature initialized")

    def get_required_components(self) -> List[Dict[str, Any]]:
        """Define required Neo4j component for graph caching."""
        return [
            {
                "component_type": "neo4j",
                "component_id": "graph_cache_neo4j",
                "config": {
                    "uri": "bolt://localhost:7687",
                    "user": "neo4j",
                    "password": "testpassword",
                    "name": "graph_cache_db"
                },
                "optional": False
            }
        ]

    def _setup_feature(self, component: 'component', config: Dict, component_manager) -> None:
        """Initialize graph cache with auto-created Neo4j component."""
        log.debug(f"Setting up GraphCacheFeature for component: {component.name}")
        self._component_ref = component

        # Get API key from model (existing pattern)
        api_key = self._extract_api_key(component)
        if not api_key:
            raise TypeError("Graph cache requires API key from model configuration.")

        # Get or create Neo4j component through component manager
        neo4j_config = {
            "uri": config.get("graph_cache_uri", "bolt://localhost:7687"),
            "user": config.get("graph_cache_user", "neo4j"),
            "password": config.get("graph_cache_password", "testpassword"),
            "name": f"{component.name}_cache",
            "api_key": api_key
        }

        log.debug(f"Creating Neo4j component with config: {neo4j_config}")
        self._neo4j_component = component_manager.get_or_create_component(
            component_id=f"{component.name}_graph_cache_neo4j",
            component_type="neo4j",
            config=neo4j_config
        )

        # Initialize vector index if not already done
        try:
            self._neo4j_component.init_vector_index(
                index_name="embeddings",
                label="Prompt",
                property="embedding"
            )
            log.debug("Vector index initialized successfully")
        except Exception as e:
            # Index might already exist, which is fine
            log.debug(f"Vector index initialization: {e}")

        # Attach to component for access
        component._graph_cache = self._neo4j_component
        component._cache_mode = True
        log.info(f"Graph cache feature setup complete for component: {component.name}")

    def teardown(self, component: 'component', component_manager) -> None:
        """Clean up graph cache (component manager handles Neo4j cleanup)."""
        log.debug(f"Tearing down GraphCacheFeature for component: {component.name}")

        # Remove references from component
        if hasattr(component, '_graph_cache'):
            delattr(component, '_graph_cache')
        if hasattr(component, '_cache_mode'):
            delattr(component, '_cache_mode')

        # Component manager will handle actual Neo4j component cleanup
        self._neo4j_component = None
        log.debug(f"GraphCacheFeature teardown complete for component: {component.name}")

    def get_hooks(self) -> List[Tuple[str, Callable]]:
        """Return cache-related hooks."""
        return [
            ("agent.action", self._log_action_hook),
            ("agent.step_complete", self._cache_workflow_hook)
        ]

    def get_pipes(self) -> List[Tuple[str, Callable]]:
        """Return cache-related pipes."""
        return [
            ("input.received", self._check_cache_pipe)
        ]

    def _extract_api_key(self, component) -> str:
        """Extract API key from component's model."""
        if hasattr(component, 'model') and hasattr(component.model, '_api_key'):
            return component.model._api_key
        return None

    def _check_cache_pipe(self, payload: InputReceivedPayload) -> InputReceivedPayload:
        """Check cache for similar queries and potentially modify input."""
        if not self._neo4j_component:
            return payload

        try:
            log.debug(f"Checking cache for input: {payload.input[:50]}...")
            # Implementation for cache lookup
            similar_results = self._neo4j_component.similarity_search(
                payload.input, "Prompt", "value"
            )

            if similar_results and similar_results[0].get("score", 0) > 0.9:
                log.debug("High confidence cache hit found")
                # High confidence cache hit - could modify payload or set flag
                payload.cache_hit = True
                payload.cached_actions = self._extract_cached_actions(similar_results[0])
        except Exception as e:
            # Cache lookup failed, continue without cache
            log.debug(f"Cache lookup failed: {e}")

        return payload

    def _extract_cached_actions(self, result: Dict) -> List[str]:
        """Extract cached actions from similarity search result."""
        return result.get("actions", [])

    def _log_action_hook(self, payload: AgentActionPayload) -> None:
        """Log actions for future caching."""
        if not self._neo4j_component:
            return

        try:
            log.debug(f"Logging action for caching: {payload.action}")
            # Store action in graph for future cache hits
            self._neo4j_component.create_node(
                "Action",
                {
                    "action": payload.action,
                    "component_id": payload.component_id,
                    "timestamp": payload.timestamp if hasattr(payload, 'timestamp') else None
                }
            )
        except Exception as e:
            # Action logging failed, continue without error
            log.debug(f"Action logging failed: {e}")

    def _cache_workflow_hook(self, payload: AgentStepCompletePayload) -> None:
        """Cache completed workflow."""
        if not self._neo4j_component:
            return

        try:
            log.debug(f"Caching workflow completion for component: {payload.component_id}")
            # Store completed workflow for future retrieval
            self._neo4j_component.create_node(
                "Workflow",
                {
                    "component_id": payload.component_id,
                    "result": payload.result if hasattr(payload, 'result') else None,
                    "timestamp": payload.timestamp if hasattr(payload, 'timestamp') else None
                }
            )
        except Exception as e:
            # Workflow caching failed, continue without error
            log.debug(f"Workflow caching failed: {e}")


# Register the feature (import at module level to avoid circular imports)
def _register_feature():
    from .base import InternalFeatureRegistry
    InternalFeatureRegistry.register("graph_cache", GraphCacheFeature)

# Register when module is imported
_register_feature()