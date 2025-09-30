"""Internal Features Package for Woodwork Components."""

# Import main classes from base
from .base import InternalFeature, InternalComponentManager, InternalFeatureRegistry

# Import features to trigger registration
from .graph_cache import GraphCacheFeature
from .workflows import WorkflowsFeature

__all__ = ['InternalFeature', 'InternalComponentManager', 'InternalFeatureRegistry', 'GraphCacheFeature', 'WorkflowsFeature']