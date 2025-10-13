"""Internal Features System for Auto-Wiring Component Functionality.

This module provides a framework for automatically registering internal hooks,
pipes, and creating internal components based on component configuration flags.
"""

# Re-export classes from base to maintain backwards compatibility
from .base import InternalFeature, InternalComponentManager, InternalFeatureRegistry

__all__ = ['InternalFeature', 'InternalComponentManager', 'InternalFeatureRegistry']