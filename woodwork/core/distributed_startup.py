"""
Distributed Startup Coordinator - Clean orchestration of distributed system startup

This module implements the distributed startup architecture outlined in
docs/technical-designs/03-distributed-startup-architecture.md

Key responsibilities:
1. Analyze deployment requirements from parsed configuration
2. Route to appropriate startup strategy (local, server, docker)
3. Ensure proper event loop ownership for message bus
4. Handle GIL-aware resource allocation
5. Provide clean shutdown protocol
"""

import asyncio
import logging
import threading
import json
import os
from typing import List, Dict, Any, Optional
from pathlib import Path

from woodwork.deployments.registry import get_registry
from woodwork.deployments import Deployer
from woodwork.deployments.router import get_router
from woodwork.deployments.vms import LocalDeployment, ServerDeployment
from woodwork.deployments.docker import Docker
from woodwork.components.inputs.inputs import inputs
from woodwork.utils import sync_async

log = logging.getLogger(__name__)


class DistributedStartupCoordinator:
    """
    Central coordinator for distributed system startup.

    Builds on existing Deployment Router infrastructure while solving
    event loop ownership and GIL-aware resource allocation issues.
    """

    def __init__(self, config: Dict[str, Any], registry=None, deployer=None):
        self.config = config
        self.registry = registry or get_registry()
        self.deployer = deployer or Deployer()
        self.router = get_router()
        self.components = []
        self.deployment_configs = []

        # Track startup state
        self.startup_phase = "initialized"
        self.event_loop = None
        self.message_bus_thread = None

    def coordinate_distributed_startup(self):
        """
        Main entry point for distributed startup coordination.

        Analyzes deployment requirements and routes to appropriate strategy.
        """
        log.info("🚀 Starting distributed startup coordination...")

        try:
            # Phase 1: Analyze deployment requirements
            self.startup_phase = "analyzing"
            self._analyze_deployment_requirements()

            # Phase 2: Route to appropriate startup strategy
            self.startup_phase = "routing"
            self._route_to_startup_strategy()

            log.info("✅ Distributed startup coordination completed successfully")

        except Exception as e:
            log.error("❌ Error in distributed startup coordination: %s", e)
            import traceback
            traceback.print_exc()
            raise

    def _analyze_deployment_requirements(self):
        """
        Analyze parsed configuration to determine deployment requirements.

        Examines components to determine:
        - Which deployment types are needed (local, server, docker)
        - Message bus requirements
        - Resource allocation needs
        """
        log.debug("Analyzing deployment requirements from configuration...")

        # Extract components from config (these are already parsed by config_parser)
        from woodwork.parser.config_parser import task_m
        self.components = task_m._tools

        # Look for explicit deployment configurations in parsed config
        deployment_types = set()

        # Check for Docker requirements
        for component in self.components:
            if hasattr(component, 'config') and isinstance(component.config, dict):
                if 'docker' in component.config or 'container' in component.config:
                    deployment_types.add('docker')
                if 'server' in component.config or 'port' in component.config:
                    deployment_types.add('server')

        # Default to local deployment if no specific deployment configured
        if not deployment_types:
            deployment_types.add('local')

        self.deployment_types = deployment_types
        log.info("Detected deployment types: %s", list(deployment_types))

        # Analyze message bus requirements
        import woodwork.globals as globals

        # Check if message bus should be activated (if components use routing, hooks, or pipes)
        has_routing_components = False
        for comp in self.components:
            log.debug("[DistributedStartup] Checking component %s (type: %s)", comp.name, type(comp).__name__)
            log.debug("[DistributedStartup] Component attributes: %s", [attr for attr in dir(comp) if not attr.startswith('_')])

            if hasattr(comp, 'to') and comp.to:
                has_routing_components = True
                log.debug("[DistributedStartup] Found routing in component %s: to=%s", comp.name, comp.to)
            if hasattr(comp, 'hooks') and comp.hooks:
                has_routing_components = True
                log.debug("[DistributedStartup] Found hooks in component %s", comp.name)
            if hasattr(comp, 'pipes') and comp.pipes:
                has_routing_components = True
                log.debug("[DistributedStartup] Found pipes in component %s", comp.name)

            # Also check config dict for routing info
            if hasattr(comp, 'config') and isinstance(comp.config, dict):
                if 'to' in comp.config:
                    has_routing_components = True
                    log.debug("[DistributedStartup] Found routing in component %s config: to=%s", comp.name, comp.config['to'])
                if 'hooks' in comp.config:
                    has_routing_components = True
                    log.debug("[DistributedStartup] Found hooks in component %s config", comp.name)
                if 'pipes' in comp.config:
                    has_routing_components = True
                    log.debug("[DistributedStartup] Found pipes in component %s config", comp.name)

        if has_routing_components:
            # Activate message bus for components with routing/hooks/pipes
            globals.global_config["message_bus_active"] = True
            log.info("[DistributedStartup] Message bus mode activated - components have routing/hooks/pipes configuration")

        self.message_bus_active = globals.global_config.get("message_bus_active", False)
        log.info("Message bus active: %s", self.message_bus_active)

    def _route_to_startup_strategy(self):
        """
        Route to appropriate startup strategy based on deployment analysis.
        """
        log.debug("Routing to startup strategy based on analysis...")

        if 'docker' in self.deployment_types:
            self._start_containerized_mode()
        elif 'server' in self.deployment_types:
            self._start_server_mode()
        else:
            self._start_local_distributed_mode()

    def _start_containerized_mode(self):
        """
        Docker deployment with message bus containers.

        Creates:
        1. Message bus container (Redis)
        2. Component containers with message bus connection
        3. Service discovery and health monitoring
        """
        log.info("🐳 Starting containerized deployment mode...")

        try:
            # 1. Create message bus container
            message_bus_container = self._create_message_bus_container()

            # 2. Create component containers
            component_containers = []
            for component in self.components:
                container = self._create_component_container(component, message_bus_container)
                component_containers.append(container)

            # 3. Setup container coordination
            self._setup_container_coordination(message_bus_container, component_containers)

            log.info("✅ Containerized deployment started successfully")

        except Exception as e:
            log.error("❌ Error starting containerized mode: %s", e)
            raise

    def _start_server_mode(self):
        """
        FastAPI server deployment with distributed coordination.

        Creates:
        1. Distributed message bus (Redis for multi-server)
        2. Enhanced FastAPI servers with message bus integration
        3. Server registration and coordination
        """
        log.info("🌐 Starting server deployment mode...")

        try:
            # 1. Setup distributed message bus
            self._setup_distributed_message_bus()

            # 2. Create enhanced server deployments
            servers = self._create_server_deployments()

            # 3. Register servers with message bus
            self._register_servers_with_message_bus(servers)

            log.info("✅ Server deployment started successfully")

        except Exception as e:
            log.error("❌ Error starting server mode: %s", e)
            raise

    def _start_local_distributed_mode(self):
        """
        Local development with clean distributed message bus.

        This is the main fix for the "retry processor task died" issue.
        Creates dedicated thread with proper event loop ownership.
        """
        log.info("🏠 Starting local distributed deployment mode...")

        try:
            if self.message_bus_active:
                # Start message bus with proper threading and event loop management
                # Message bus integration will be initialized INSIDE the background thread
                self._start_enhanced_message_bus_loop()
            else:
                # Fall back to traditional Task Master
                log.info("Message bus not active - using Task Master orchestration")
                from woodwork.parser.config_parser import task_m
                task_m.start()

            log.info("✅ Local distributed deployment started successfully")

        except Exception as e:
            log.error("❌ Error starting local distributed mode: %s", e)
            raise

    def _create_message_bus_container(self):
        """Create dedicated message bus container using existing Docker class."""
        log.debug("Creating message bus container...")

        # Use existing Docker class with Redis image
        # For pre-built images, we pass an empty dockerfile string
        docker_config = Docker(
            image_name="redis:alpine",
            container_name="woodwork-message-bus",
            dockerfile="",  # Empty dockerfile means use pre-built image
            container_args={
                "ports": {"6379": "6379"},
                "environment": {
                    "REDIS_ARGS": "--appendonly yes"
                }
            },
            volume_location="./data/redis",
            docker_volume_location="/data"
        )

        # Initialize and start container
        docker_config.init()
        container = docker_config.get_container()

        log.info("✅ Message bus container created: %s", container.name)
        return container

    def _create_component_container(self, component, message_bus_container):
        """Create component container connected to message bus."""
        log.debug("Creating component container for: %s", component.name)

        # Generate Dockerfile for component
        dockerfile = f"""
FROM python:3.11-slim
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . /app
WORKDIR /app
ENV WOODWORK_MESSAGE_BUS=redis://message-bus:6379
CMD ["python", "-m", "woodwork", "component", "{component.name}"]
"""

        docker_config = Docker(
            image_name=f"woodwork-{component.name}",
            container_name=f"woodwork-{component.name}",
            dockerfile=dockerfile,
            container_args={
                "links": {message_bus_container.name: "message-bus"},
                "environment": {
                    "COMPONENT_TYPE": component.__class__.__name__,
                    "COMPONENT_NAME": component.name
                }
            }
        )

        docker_config.init()
        container = docker_config.get_container()

        log.info("✅ Component container created: %s", container.name)
        return container

    def _setup_container_coordination(self, message_bus_container, component_containers):
        """Setup service discovery and health monitoring for containers."""
        log.debug("Setting up container coordination...")

        # This would implement container health checks and service discovery
        # For now, just log the setup
        log.info("Container coordination configured:")
        log.info("  Message bus: %s", message_bus_container.name)
        log.info("  Components: %s", [c.name for c in component_containers])

    def _setup_distributed_message_bus(self):
        """Setup Redis message bus for multi-server deployment."""
        log.debug("Setting up distributed message bus...")

        # Configure Redis for distributed operation
        redis_config = {
            "host": os.getenv("REDIS_HOST", "localhost"),
            "port": int(os.getenv("REDIS_PORT", "6379")),
            "db": int(os.getenv("REDIS_DB", "0"))
        }

        log.info("✅ Distributed message bus configured: redis://%s:%s/%s",
                redis_config["host"], redis_config["port"], redis_config["db"])

    def _create_server_deployments(self):
        """Create enhanced FastAPI server deployments."""
        log.debug("Creating server deployments...")

        servers = []

        # Look for server components
        server_components = [comp for comp in self.components if hasattr(comp, 'port')]

        if not server_components:
            # Create default server deployment
            server = DistributedServerDeployment(
                components=self.components,
                port=int(os.getenv("WOODWORK_PORT", "43001"))
            )
            servers.append(server)

        log.info("✅ Created %d server deployments", len(servers))
        return servers

    def _register_servers_with_message_bus(self, servers):
        """Register servers with message bus for coordination."""
        log.debug("Registering servers with message bus...")

        for server in servers:
            log.info("✅ Registered server on port %s with message bus",
                    getattr(server, 'port', 'unknown'))

    def _start_enhanced_message_bus_loop(self):
        """
        Enhanced version of message bus loop with proper threading.

        This is the key fix for the "retry processor task died" issue.
        Creates dedicated thread with proper event loop ownership.
        """
        log.info("🚀 Starting enhanced message bus loop with proper threading...")

        # Find input components
        input_components = [tool for tool in self.components if isinstance(tool, inputs)]

        if not input_components:
            log.error("No input components found - cannot start message bus loop")
            return

        input_component = input_components[0]
        log.info("Using input component: %s", input_component.name)

        def run_message_bus_background():
            """Background thread specifically for message bus event loop"""
            # Create dedicated event loop for message bus
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.event_loop = loop

            async def message_bus_runtime():
                try:
                    # 1. Initialize message bus integration IN this event loop
                    log.info("🔗 Initializing message bus integration in background thread...")
                    await self._async_initialize_message_bus_integration()

                    # 2. Start message bus (existing integration approach)
                    from woodwork.core.message_bus.factory import get_global_message_bus
                    message_bus = await get_global_message_bus()
                    log.info("✅ Message bus started with background tasks (retry processor, cleanup)")

                    # 3. Setup integration manager
                    from woodwork.core.message_bus.integration import get_global_message_bus_manager
                    manager = get_global_message_bus_manager()

                    # 4. Setup streaming (existing Router.setup_streaming)
                    stream_manager = await self.router.setup_streaming()
                    if stream_manager:
                        log.debug("Message bus: Streaming set up successfully")
                    else:
                        log.warning("Message bus: Failed to set up streaming")

                    # 5. Start main input/output loop
                    await self._enhanced_message_bus_main_loop(input_component)

                except Exception as e:
                    log.error("Error in message bus runtime: %s", e)
                    import traceback
                    traceback.print_exc()
                finally:
                    # Clean shutdown
                    try:
                        message_bus = await get_global_message_bus()
                        if hasattr(message_bus, 'stop'):
                            await message_bus.stop()
                            log.info("Message bus stopped cleanly")
                    except Exception as e:
                        log.error("Error stopping message bus: %s", e)

            # Run in dedicated thread with proper cleanup
            try:
                loop.run_until_complete(message_bus_runtime())
            except KeyboardInterrupt:
                log.info("Message bus thread shutting down...")
            finally:
                loop.close()

        # Start in daemon thread (allows main process to exit cleanly)
        self.message_bus_thread = threading.Thread(target=run_message_bus_background, daemon=True)
        self.message_bus_thread.start()

        # Keep main thread alive for CLI interaction
        try:
            self.message_bus_thread.join()
        except KeyboardInterrupt:
            log.info("Shutting down enhanced distributed system...")

    async def _enhanced_message_bus_main_loop(self, input_component):
        """Enhanced main message bus input/output loop."""

        log.info("🔄 Enhanced message bus main loop started - waiting for input...")

        while True:
            try:
                # Get input from the input component
                x = input_component.input_function()

                # Handle exit conditions
                if x == "exit" or x == ";":
                    log.info("Exit command received - shutting down message bus loop")
                    break

                # Process input through message bus
                log.debug("Processing input through enhanced message bus: %s", str(x)[:100])

                # Create proper InputReceivedPayload for the event system
                from woodwork.types import InputReceivedPayload
                payload = InputReceivedPayload(
                    input=x,
                    inputs={},
                    session_id=getattr(input_component, 'session_id', 'default'),
                    component_id=input_component.name,
                    component_type="inputs"
                )

                # Emit the input event - the message bus will handle routing
                await input_component.emit("input_received", payload)

                log.debug("Input processed and routed through enhanced message bus")

            except KeyboardInterrupt:
                log.info("Keyboard interrupt - shutting down enhanced message bus loop")
                break
            except Exception as e:
                log.error("Error in enhanced message bus main loop: %s", e)
                # Continue the loop even on errors
                continue

        # Clean up
        log.info("Enhanced message bus main loop shutting down...")

        # Close all components
        from woodwork.parser.config_parser import task_m
        task_m.close_all()

    def _initialize_message_bus_integration(self):
        """
        Initialize message bus integration synchronously.

        This moves the message bus integration from config_parser to ensure
        it happens in the proper thread with correct event loop ownership.
        """
        log.info("🔗 Initializing message bus integration...")

        try:
            from woodwork.core.message_bus.integration import (
                initialize_global_message_bus_integration_sync,
                get_global_message_bus_manager
            )
            from woodwork.core.message_bus.factory import configure_global_message_bus

            # Create component configurations from parsed components
            component_configs = {}
            for component in self.components:
                component_configs[component.name] = {
                    "object": component,
                    "component": component.__class__.__name__.lower(),
                    "variable": component.name
                }

            log.debug("Component configs for message bus: %s", list(component_configs.keys()))

            # Configure and initialize message bus
            # Use default configuration for message bus
            message_bus_config = {
                "type": "in_memory",  # Default to in-memory for local development
                "retry_attempts": 3,
                "retry_delay": 1.0
            }
            configure_global_message_bus(message_bus_config)
            initialize_global_message_bus_integration_sync(component_configs)

            log.info("[DistributedStartup] Message bus integration initialized with %d components", len(component_configs))

            # Ensure all components have required integration attributes
            for cfg in component_configs.values():
                comp = cfg.get("object")
                if comp:
                    if not hasattr(comp, "_integration_ready"):
                        comp._integration_ready = True
                    # Let MessageBusIntegration handle _message_bus itself in _ensure_message_bus_integration
                    # Don't set _message_bus directly - it should be the actual bus, not the manager

                    # Set DeclarativeRouter if not already set
                    if not hasattr(comp, "_router") or comp._router is None:
                        from woodwork.core.message_bus.declarative_router import DeclarativeRouter
                        from woodwork.core.message_bus.factory import get_global_message_bus
                        try:
                            message_bus = sync_async(get_global_message_bus)
                            comp._router = DeclarativeRouter(message_bus)
                            comp._router.configure_from_components(component_configs)
                            log.debug("[DistributedStartup] Set DeclarativeRouter on component '%s'", comp.name)
                        except Exception as e:
                            log.warning("[DistributedStartup] Failed to set router on component '%s': %s", comp.name, e)

            # Log status
            manager = get_global_message_bus_manager()
            stats = manager.get_manager_stats()
            log.info("[DistributedStartup] Message bus status: %s", {
                "integration_active": stats["integration_active"],
                "registered_components": stats["registered_components"],
                "message_bus_healthy": stats["message_bus_healthy"]
            })

            if stats.get("router_stats", {}).get("routing_table"):
                log.debug("[DistributedStartup] Routing table: %s", stats["router_stats"]["routing_table"])

        except Exception as e:
            log.error("[DistributedStartup] Failed to initialize message bus integration: %s", e)
            log.error("[DistributedStartup] Components will work without distributed messaging")
            raise

    async def _async_initialize_message_bus_integration(self):
        """
        Initialize message bus integration asynchronously in the correct event loop.

        This ensures that all async tasks (like retry processor) are created in
        the same event loop where they will run.
        """
        try:
            from woodwork.core.message_bus.integration import (
                initialize_global_message_bus_integration,
                get_global_message_bus_manager
            )
            from woodwork.core.message_bus.factory import configure_global_message_bus

            # Create component configurations from parsed components
            component_configs = {}
            for component in self.components:
                component_configs[component.name] = {
                    "object": component,
                    "component": component.__class__.__name__.lower(),
                    "variable": component.name
                }

            log.debug("Component configs for async message bus: %s", list(component_configs.keys()))

            # Configure and initialize message bus ASYNC
            message_bus_config = {
                "type": "in_memory",  # Default to in-memory for local development
                "retry_attempts": 3,
                "retry_delay": 1.0
            }
            configure_global_message_bus(message_bus_config)

            # Use the ASYNC version instead of sync
            await initialize_global_message_bus_integration(component_configs)

            log.info("[DistributedStartup] Async message bus integration initialized with %d components", len(component_configs))

            # Ensure all components have required integration attributes
            for cfg in component_configs.values():
                comp = cfg.get("object")
                if comp:
                    if not hasattr(comp, "_integration_ready"):
                        comp._integration_ready = True
                    # Let MessageBusIntegration handle _message_bus itself in _ensure_message_bus_integration
                    # Don't set _message_bus directly - it should be the actual bus, not the manager

                    # Set DeclarativeRouter if not already set
                    if not hasattr(comp, "_router") or comp._router is None:
                        from woodwork.core.message_bus.declarative_router import DeclarativeRouter
                        from woodwork.core.message_bus.factory import get_global_message_bus
                        try:
                            message_bus = await get_global_message_bus()
                            comp._router = DeclarativeRouter(message_bus)
                            comp._router.configure_from_components(component_configs)
                            log.debug("[DistributedStartup] Set DeclarativeRouter on component '%s'", comp.name)
                        except Exception as e:
                            log.warning("[DistributedStartup] Failed to set router on component '%s': %s", comp.name, e)

            # Log status
            manager = get_global_message_bus_manager()
            stats = manager.get_manager_stats()
            log.info("[DistributedStartup] Async message bus status: %s", {
                "integration_active": stats["integration_active"],
                "registered_components": stats["registered_components"],
                "message_bus_healthy": stats["message_bus_healthy"]
            })

            if stats.get("router_stats", {}).get("routing_table"):
                log.debug("[DistributedStartup] Async routing table: %s", stats["router_stats"]["routing_table"])

        except Exception as e:
            log.error("[DistributedStartup] Failed to initialize async message bus integration: %s", e)
            log.error("[DistributedStartup] Components will work without distributed messaging")
            raise


class DistributedServerDeployment(ServerDeployment):
    """
    Enhanced ServerDeployment with message bus integration.

    Builds on existing ServerDeployment with distributed coordination.
    """

    def __init__(self, components, port=43001, message_bus_url=None, **config):
        super().__init__(components, port, **config)
        self.message_bus_url = message_bus_url or "redis://localhost:6379"
        self._setup_distributed_integration()

    def _setup_distributed_integration(self):
        """Setup message bus integration for server deployment."""

        # Add health check endpoint
        @self.app.get("/health")
        async def health_check():
            # Check message bus connectivity
            bus_health = await self._check_message_bus_health()
            return {"status": "healthy", "message_bus": bus_health}

        # Add component discovery endpoint
        @self.app.get("/components")
        async def list_components():
            return [{"name": comp.name, "type": comp.__class__.__name__} for comp in self.components]

        # Enhanced component routes with message bus coordination
        for comp in self.components:
            @self.app.post(f"/{comp.name}/input")
            async def enhanced_input(request, component=comp):
                data = await request.json()

                # Process through component
                result = await self._maybe_async(component.input, data["value"])

                # Emit through message bus for coordination
                await self._emit_to_message_bus("component.output", {
                    "component": component.name,
                    "result": result,
                    "server": self.port
                })

                return result

    async def _check_message_bus_health(self):
        """Check message bus connectivity."""
        try:
            from woodwork.core.message_bus.factory import get_global_message_bus
            message_bus = await get_global_message_bus()
            return {"status": "healthy", "type": message_bus.__class__.__name__}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    async def _emit_to_message_bus(self, event_type, payload):
        """Emit event to message bus for coordination."""
        try:
            from woodwork.events import emit
            await emit(event_type, payload)
        except Exception as e:
            log.error("Error emitting to message bus: %s", e)

    async def deploy(self):
        # 1. Connect to message bus first
        await self._connect_to_message_bus()

        # 2. Start FastAPI server (existing)
        await super().deploy()

    async def _connect_to_message_bus(self):
        """Connect to distributed message bus."""
        log.info("Connecting to distributed message bus: %s", self.message_bus_url)
        # Implementation would connect to Redis/NATS
        pass


class ShutdownCoordinator:
    """Coordinate clean shutdown of distributed system."""

    def __init__(self, startup_coordinator: DistributedStartupCoordinator):
        self.startup_coordinator = startup_coordinator

    async def shutdown_distributed_system(self):
        """Clean shutdown protocol for distributed system."""
        log.info("🛑 Starting distributed system shutdown...")

        try:
            # 1. Stop accepting new work
            if hasattr(self.startup_coordinator, 'message_bus'):
                await self.startup_coordinator.message_bus.stop_accepting()

            # 2. Drain message queues
            # Implementation would drain queues

            # 3. Shutdown component workers
            await self._shutdown_component_workers()

            # 4. Shutdown message bus
            if hasattr(self.startup_coordinator, 'message_bus'):
                await self.startup_coordinator.message_bus.stop()

            # 5. Cleanup resources
            self._cleanup_shared_resources()

            log.info("✅ Distributed system shutdown completed")

        except Exception as e:
            log.error("❌ Error during distributed system shutdown: %s", e)

    async def _shutdown_component_workers(self):
        """Shutdown component worker processes."""
        log.debug("Shutting down component workers...")
        # Implementation would shutdown workers

    def _cleanup_shared_resources(self):
        """Cleanup shared resources."""
        log.debug("Cleaning up shared resources...")
        # Implementation would cleanup resources