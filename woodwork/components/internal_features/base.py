"""Base classes for Internal Features System."""

import logging
from typing import Dict, List, Callable, Type, Optional, Any, Tuple
from abc import ABC, abstractmethod

log = logging.getLogger(__name__)


class InternalFeature(ABC):
    """Base class for internal features that can be auto-wired to components."""

    def setup(self, component: 'component', config: Dict, component_manager: 'InternalComponentManager') -> None:
        """Setup the feature for the given component."""
        # Call feature-specific setup
        self._setup_feature(component, config, component_manager)
        # Automatically register hooks and pipes with UnifiedEventBus
        self._register_hooks_and_pipes()

    @abstractmethod
    def _setup_feature(self, component: 'component', config: Dict, component_manager: 'InternalComponentManager') -> None:
        """Setup the specific feature implementation. Override this instead of setup()."""
        pass

    def _register_hooks_and_pipes(self):
        """Register this feature's hooks and pipes with the UnifiedEventBus."""
        try:
            from woodwork.core.unified_event_bus import get_global_event_bus
            event_bus = get_global_event_bus()

            # Register hooks
            hooks = self.get_hooks()
            for event_name, hook_function in hooks:
                event_bus.register_hook(event_name, hook_function)
                log.debug(f"Registered hook for event '{event_name}' from feature {self.__class__.__name__}")

            # Register pipes
            pipes = self.get_pipes()
            for event_name, pipe_function in pipes:
                event_bus.register_pipe(event_name, pipe_function)
                log.debug(f"Registered pipe for event '{event_name}' from feature {self.__class__.__name__}")

        except Exception as e:
            log.warning(f"Failed to register hooks/pipes for feature {self.__class__.__name__}: {e}")

    @abstractmethod
    def teardown(self, component: 'component', component_manager: 'InternalComponentManager') -> None:
        """Clean up the feature when component closes."""
        pass

    @abstractmethod
    def get_hooks(self) -> List[Tuple[str, Callable]]:
        """Return list of (event_name, hook_function) tuples."""
        pass

    @abstractmethod
    def get_pipes(self) -> List[Tuple[str, Callable]]:
        """Return list of (event_name, pipe_function) tuples."""
        pass

    @abstractmethod
    def get_required_components(self) -> List[Dict[str, Any]]:
        """Return list of component specs this feature requires.

        Each spec is a dict with:
        - component_type: str (e.g., 'neo4j', 'chroma')
        - component_id: str (unique identifier)
        - config: Dict (component configuration)
        - optional: bool (whether component is optional, default False)
        """
        pass


class InternalComponentManager:
    """Manages auto-created internal components for features."""

    def __init__(self, async_runtime=None):
        self._components: Dict[str, Any] = {}

        # Use provided runtime or try to get global runtime
        if async_runtime is not None:
            self._async_runtime = async_runtime
        else:
            try:
                from woodwork.core.async_runtime import get_global_runtime
                self._async_runtime = get_global_runtime()
                log.debug("InternalComponentManager using global AsyncRuntime")
            except Exception as e:
                log.debug(f"Could not access global AsyncRuntime: {e}")
                self._async_runtime = None

        log.debug("InternalComponentManager initialized with modern AsyncRuntime support")

    def get_or_create_component(self, component_id: str, component_type: str, config: Dict) -> Any:
        """Get existing component or create new one if not exists."""
        if component_id in self._components:
            log.debug(f"Returning existing component: {component_id}")
            return self._components[component_id]

        log.debug(f"Creating new component: {component_id} of type {component_type}")
        component = self._create_component(component_type, config)
        self._components[component_id] = component

        # Register with modern AsyncRuntime
        if self._async_runtime and hasattr(self._async_runtime, 'register_internal_component'):
            log.debug(f"Registering component {component_id} with AsyncRuntime")
            self._async_runtime.register_internal_component(component_id, component)
        else:
            log.debug(f"No AsyncRuntime available for component {component_id} registration")

        return component

    def _create_component(self, component_type: str, config: Dict) -> Any:
        """Create component instance based on type."""
        log.debug(f"Creating component of type: {component_type} with config: {config}")

        component_factories = {}

        # Try to import and register Neo4j factory
        try:
            from woodwork.components.knowledge_bases.graph_databases.neo4j import neo4j
            component_factories['neo4j'] = neo4j
            log.debug("Neo4j component factory registered")
        except ImportError as e:
            log.debug(f"Neo4j component factory not available: {e}")

        # Try to import and register Chroma factory
        try:
            from woodwork.components.knowledge_bases.vector_databases.chroma import chroma
            component_factories['chroma'] = chroma
            log.debug("Chroma component factory registered")
        except ImportError as e:
            log.debug(f"Chroma component factory not available: {e}")

        # Add more component types as needed

        if component_type not in component_factories:
            raise ValueError(f"Unknown internal component type: {component_type}")

        factory = component_factories[component_type]
        return factory(**config)

    def get_component(self, component_id: str) -> Optional[Any]:
        """Get existing component by ID."""
        return self._components.get(component_id)

    def cleanup_components(self) -> None:
        """Clean up all managed components."""
        log.debug(f"Cleaning up {len(self._components)} internal components")
        for component_id, component in self._components.items():
            try:
                if hasattr(component, 'close'):
                    log.debug(f"Closing component: {component_id}")
                    component.close()
            except Exception as e:
                log.warning(f"Error closing component {component_id}: {e}")
        self._components.clear()

    async def startup_internal_components(self) -> None:
        """Start all internal components that support async startup."""
        log.debug(f"Starting {len(self._components)} internal components")
        import asyncio

        startup_tasks = []
        for component_id, component in self._components.items():
            if hasattr(component, 'start') and asyncio.iscoroutinefunction(component.start):
                log.debug(f"Scheduling async startup for component: {component_id}")
                startup_tasks.append(component.start())
            elif hasattr(component, 'start'):
                log.debug(f"Starting sync component: {component_id}")
                try:
                    component.start()
                except Exception as e:
                    log.warning(f"Error starting component {component_id}: {e}")

        # Wait for all async startups to complete
        if startup_tasks:
            try:
                await asyncio.gather(*startup_tasks)
                log.debug("All internal components started successfully")
            except Exception as e:
                log.error(f"Error during internal component startup: {e}")

    def get_all_components(self) -> Dict[str, Any]:
        """Get all managed components for integration with AsyncRuntime."""
        return self._components.copy()


class InternalFeatureRegistry:
    """Registry mapping config flags to internal features."""

    _features: Dict[str, Type[InternalFeature]] = {}

    @classmethod
    def register(cls, config_key: str, feature_class: Type[InternalFeature]):
        """Register a feature class for a config key."""
        class_name = getattr(feature_class, '__name__', str(feature_class))
        log.debug(f"Registering internal feature: {config_key} -> {class_name}")
        cls._features[config_key] = feature_class

    @classmethod
    def create_features(cls, config: Dict) -> List[InternalFeature]:
        """Create feature instances based on config flags."""
        # Ensure all features are loaded
        cls._ensure_features_loaded()

        features = []
        for key, feature_class in cls._features.items():
            if config.get(key, False):
                log.debug(f"Creating internal feature: {key}")
                features.append(feature_class())

        log.debug(f"Created {len(features)} internal features")
        return features

    @classmethod
    def get_registered_features(cls) -> Dict[str, Type[InternalFeature]]:
        """Get all registered features for debugging."""
        return cls._features.copy()

    @classmethod
    def _ensure_features_loaded(cls):
        """Ensure all available features are loaded and registered."""
        try:
            # Import graph_cache feature to trigger registration
            from woodwork.components.internal_features.graph_cache import GraphCacheFeature
        except ImportError as e:
            log.debug(f"Could not import GraphCacheFeature: {e}")

        try:
            # Import knowledge_graph feature to trigger registration
            from woodwork.components.internal_features.knowledge_graph import KnowledgeGraphFeature
        except ImportError as e:
            log.debug(f"Could not import KnowledgeGraphFeature: {e}")

        # Add imports for other features as they are created