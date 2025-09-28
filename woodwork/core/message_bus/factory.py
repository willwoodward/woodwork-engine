"""
Message Bus Factory with Intelligent Defaults

Provides zero-configuration message bus creation with intelligent defaults based on
environment and optional advanced configuration for power users.
"""

import os
import logging
from typing import Dict, Any, Optional

from .interface import MessageBusInterface
from .in_memory_bus import InMemoryMessageBus

log = logging.getLogger(__name__)


class MessageBusFactory:
    """Factory for creating message bus instances with intelligent defaults"""
    
    @staticmethod
    def create_message_bus(config: Optional[Dict[str, Any]] = None) -> MessageBusInterface:
        """
        Create message bus instance based on configuration
        
        Args:
            config: Optional configuration dict. If None, uses intelligent defaults.
            
        Returns:
            MessageBusInterface implementation
        """
        if config is None:
            config = {}
        
        bus_type = config.get("type", "auto")
        
        if bus_type == "auto":
            # Intelligent defaults based on environment
            return MessageBusFactory._create_auto_bus(config)
        elif bus_type == "memory" or bus_type == "in_memory":
            return MessageBusFactory._create_in_memory_bus(config)
        elif bus_type == "redis":
            return MessageBusFactory._create_redis_bus(config)
        elif bus_type == "nats":
            return MessageBusFactory._create_nats_bus(config)
        else:
            raise ValueError(f"Unknown message bus type: {bus_type}")
    
    @staticmethod
    def _create_auto_bus(config: Dict[str, Any]) -> MessageBusInterface:
        """Create message bus with intelligent defaults"""
        
        # Check environment variables for deployment hints
        env = os.getenv('WOODWORK_ENV', 'development').lower()
        
        log.debug("[MessageBusFactory] Auto-detecting message bus for environment: %s", env)
        
        if env == 'development' or env == 'dev':
            # Development: Fast in-memory bus for iteration
            log.info("[MessageBusFactory] Using in-memory message bus for development")
            return MessageBusFactory._create_in_memory_bus(config)
        
        elif env in ['production', 'prod', 'staging']:
            # Production: Try Redis, fallback to in-memory with warning
            redis_url = os.getenv('REDIS_URL')
            if redis_url:
                try:
                    log.info("[MessageBusFactory] Using Redis message bus for production")
                    redis_config = {**config, "redis_url": redis_url, "type": "redis"}
                    return MessageBusFactory._create_redis_bus(redis_config)
                except Exception as e:
                    log.warning("[MessageBusFactory] Redis unavailable (%s), falling back to in-memory", e)
            else:
                log.warning("[MessageBusFactory] No REDIS_URL in production environment")
            
            # Fallback to in-memory with warning
            log.warning("[MessageBusFactory] Using in-memory message bus in production - not recommended for scaling")
            return MessageBusFactory._create_in_memory_bus(config)
        
        elif env == 'cloud':
            # Cloud: Prefer NATS, fallback to Redis, then in-memory
            nats_url = os.getenv('NATS_URL')
            redis_url = os.getenv('REDIS_URL')
            
            if nats_url:
                try:
                    log.info("[MessageBusFactory] Using NATS message bus for cloud deployment")
                    nats_config = {**config, "nats_url": nats_url, "type": "nats"}
                    return MessageBusFactory._create_nats_bus(nats_config)
                except Exception as e:
                    log.warning("[MessageBusFactory] NATS unavailable (%s), trying Redis", e)
            
            if redis_url:
                try:
                    log.info("[MessageBusFactory] Using Redis message bus for cloud deployment")
                    redis_config = {**config, "redis_url": redis_url, "type": "redis"}
                    return MessageBusFactory._create_redis_bus(redis_config)
                except Exception as e:
                    log.warning("[MessageBusFactory] Redis unavailable (%s), falling back to in-memory", e)
            
            log.warning("[MessageBusFactory] No cloud message bus available, using in-memory")
            return MessageBusFactory._create_in_memory_bus(config)
        
        else:
            # Unknown environment: Default to in-memory
            log.info("[MessageBusFactory] Unknown environment '%s', using in-memory message bus", env)
            return MessageBusFactory._create_in_memory_bus(config)
    
    @staticmethod
    def _create_in_memory_bus(config: Dict[str, Any]) -> MessageBusInterface:
        """Create in-memory message bus with configuration"""
        
        # Extract configuration with defaults
        max_queue_size = config.get("max_queue_size", 10000)
        max_retries = config.get("max_retries", 3)
        
        log.debug("[MessageBusFactory] Creating InMemoryMessageBus: queue_size=%d, retries=%d", 
                  max_queue_size, max_retries)
        
        return InMemoryMessageBus(
            max_queue_size=max_queue_size,
            max_retries=max_retries
        )
    
    @staticmethod
    def _create_redis_bus(config: Dict[str, Any]) -> MessageBusInterface:
        """Create Redis message bus (future implementation)"""
        log.error("[MessageBusFactory] Redis message bus not yet implemented")
        
        # For now, fallback to in-memory with Redis-like configuration
        log.warning("[MessageBusFactory] Falling back to in-memory bus until Redis implementation ready")
        return MessageBusFactory._create_in_memory_bus({
            **config,
            "max_queue_size": config.get("max_queue_size", 50000),  # Higher capacity for Redis-like usage
            "max_retries": config.get("max_retries", 5)
        })
    
    @staticmethod
    def _create_nats_bus(config: Dict[str, Any]) -> MessageBusInterface:
        """Create NATS message bus (future implementation)"""
        log.error("[MessageBusFactory] NATS message bus not yet implemented")
        
        # For now, fallback to in-memory with NATS-like configuration
        log.warning("[MessageBusFactory] Falling back to in-memory bus until NATS implementation ready")
        return MessageBusFactory._create_in_memory_bus({
            **config,
            "max_queue_size": config.get("max_queue_size", 100000),  # Higher capacity for NATS-like usage
            "max_retries": config.get("max_retries", 10)
        })


# Global message bus instance for zero-configuration usage
_global_message_bus: Optional[MessageBusInterface] = None
_bus_config: Optional[Dict[str, Any]] = None


def create_default_message_bus() -> MessageBusInterface:
    """
    Create message bus with intelligent defaults based on environment
    
    This function encapsulates all the intelligence for choosing the right
    message bus without any user configuration required.
    """
    
    log.debug("[MessageBusFactory] Creating default message bus")
    
    # Use factory with auto-detection
    return MessageBusFactory.create_message_bus({"type": "auto"})


async def get_global_message_bus() -> MessageBusInterface:
    """
    Get or create global message bus instance
    
    This provides a singleton message bus that components can use without
    any configuration. The bus is automatically started when first accessed.
    """
    global _global_message_bus
    
    if _global_message_bus is None:
        log.debug("[MessageBusFactory] Creating global message bus instance")
        _global_message_bus = create_default_message_bus()
        
        # Start the bus automatically
        await _global_message_bus.start()
        
        log.info("[MessageBusFactory] Global message bus started: %s", 
                 type(_global_message_bus).__name__)
    
    return _global_message_bus


def set_global_message_bus(message_bus: MessageBusInterface) -> None:
    """
    Set custom global message bus instance
    
    This allows advanced users or deployment configurations to override
    the default message bus with a custom implementation.
    
    Args:
        message_bus: Custom message bus instance
    """
    global _global_message_bus
    
    if _global_message_bus is not None:
        log.warning("[MessageBusFactory] Replacing existing global message bus")
    
    _global_message_bus = message_bus
    
    log.info("[MessageBusFactory] Set custom global message bus: %s", 
             type(message_bus).__name__)


async def shutdown_global_message_bus() -> None:
    """
    Shutdown and cleanup global message bus
    
    This should be called during application shutdown to ensure
    clean resource cleanup.
    """
    global _global_message_bus
    
    if _global_message_bus is not None:
        log.info("[MessageBusFactory] Shutting down global message bus")
        await _global_message_bus.stop()
        _global_message_bus = None
    else:
        log.debug("[MessageBusFactory] No global message bus to shutdown")


def configure_global_message_bus(config: Dict[str, Any]) -> None:
    """
    Configure global message bus before first use

    This allows deployment configurations to customize the message bus
    before any components try to use it.

    Args:
        config: Message bus configuration

    Note:
        If called after global message bus has been created, this will log
        a warning but not raise an error to support component initialization order.
    """
    global _bus_config

    if _global_message_bus is not None:
        log.warning("[MessageBusFactory] Global message bus already created, configuration ignored: %s", config)
        return

    _bus_config = config

    log.debug("[MessageBusFactory] Configured global message bus: %s", config)


def get_message_bus_config() -> Optional[Dict[str, Any]]:
    """Get current message bus configuration"""
    return _bus_config


# Convenience functions for common configuration patterns
def configure_for_development():
    """Configure message bus for development environment"""
    configure_global_message_bus({
        "type": "memory",
        "max_queue_size": 1000,
        "max_retries": 2
    })
    log.info("[MessageBusFactory] Configured for development")


def configure_for_production(redis_url: str):
    """Configure message bus for production environment with Redis"""
    configure_global_message_bus({
        "type": "redis", 
        "redis_url": redis_url,
        "max_queue_size": 50000,
        "max_retries": 5,
        "stream_prefix": os.getenv("WOODWORK_STREAM_PREFIX", "woodwork"),
        "consumer_group": os.getenv("WOODWORK_CONSUMER_GROUP", "components")
    })
    log.info("[MessageBusFactory] Configured for production with Redis")


def configure_for_cloud(nats_url: str):
    """Configure message bus for cloud environment with NATS"""
    configure_global_message_bus({
        "type": "nats",
        "nats_url": nats_url,
        "max_queue_size": 100000,
        "max_retries": 10,
        "stream_prefix": os.getenv("WOODWORK_STREAM_PREFIX", "woodwork"),
        "consumer_group": os.getenv("WOODWORK_CONSUMER_GROUP", "components")
    })
    log.info("[MessageBusFactory] Configured for cloud with NATS")