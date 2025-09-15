# Distributed Startup Architecture Design

## Executive Summary

This document analyzes the current chaotic startup sequence in Woodwork's distributed message bus system and proposes a clean, GIL-aware, parallelizable architecture that can safely handle async components, threading, and multiprocessing without the current event loop conflicts and task lifecycle issues.

## Current Problem: The Startup Mess

### The Chaos We Have Today

The current startup sequence is a disaster of overlapping concerns, conflicting event loops, and race conditions:

```
CLI Entry → Config Parse → Message Bus Init → Threading → AsyncIO → Multiprocessing → Task Master → Message Bus Loop
     ↓            ↓              ↓             ↓         ↓           ↓              ↓              ↓
  Sync Code   Sync Parser   Thread Pool   Background   New Loop   Process Pool   Sync Start   Background Thread
                              Executor      Thread                   Workers                    + Event Loop
```

### Specific Issues Identified

1. **Event Loop Confusion**: Message bus initialized in `ThreadPoolExecutor` → tasks created in temp event loop → loop destroyed → "Retry processor task died"

2. **Mixed Sync/Async Patterns**:
   - `config_parser.py` is sync but calls async message bus init
   - `integration.py` has `initialize_global_message_bus_integration_sync()` that creates threads to run async code
   - Main loop tries to bridge sync CLI with async message bus

3. **Threading vs Multiprocessing Conflict**:
   - Components use `multiprocessing.Queue` for progress tracking
   - Message bus needs async tasks in same thread
   - Python GIL makes threading suboptimal for CPU-bound work

4. **Lifecycle Management Chaos**:
   ```python
   # This is the actual sequence today:
   config_parser.main_function()              # Sync
   → _initialize_message_bus_integration()    # Sync calling async
   → initialize_global_message_bus_integration_sync()  # Thread pool!
   → ThreadPoolExecutor.submit(asyncio.run()) # New event loop
   → Message bus starts in temp loop          # Tasks created
   → Thread pool shuts down                   # Event loop destroyed!
   → start_message_bus_loop()                 # New thread, new loop
   → get_global_message_bus()                 # Tries to use dead tasks
   ```

5. **Resource Leaks**: Multiple event loops, unclosed threads, orphaned async tasks

## Root Cause Analysis

The fundamental issue is **trying to bolt async distributed messaging onto a synchronous, multiprocess-parallel component system**. We have:

- **Legacy**: Sync config parser + multiprocess component lifecycle
- **New**: Async message bus with background tasks
- **Bridge**: Hacky thread pools and sync wrappers

This creates an **impedance mismatch** where neither system can work optimally.

## Proposed Solution: Clean Distributed Architecture

### Core Principles

1. **Separation of Concerns**: Clear boundaries between sync startup, async runtime, and deployment management
2. **GIL Awareness**: Use threading for I/O (message bus), multiprocessing for CPU (component init)
3. **Event Loop Ownership**: One master event loop owns all async tasks
4. **Deployment Flexibility**: Support local, server, and Docker deployments seamlessly
5. **Graceful Degradation**: System works with or without message bus

### Architecture Overview (Aligned with Existing Scope)

```
┌─────────────────────────────────────────────────────────────────┐
│                    MAIN PROCESS (CLI)                          │
│  ┌─────────────────┐  ┌────────────────────────────────────┐   │
│  │   Config        │  │     Deployment                     │   │
│  │   Parser        │  │     Registry                       │   │
│  │   (Sync)        │  │     (Existing)                     │   │
│  └─────────────────┘  └────────────────────────────────────┘   │
│                                    │                           │
│  ┌─────────────────────────────────▼───────────────────────┐   │
│  │           DISTRIBUTED STARTUP COORDINATOR               │   │
│  │        (Builds on Existing Deployment Router)          │   │
│  └─────────────────────────────────┬───────────────────────┘   │
│                                    │                           │
└────────────────────────────────────┼───────────────────────────┘
                                     │
        ┌────────────────────────────┼────────────────────────────┐
        │                DEPLOYMENT ENVIRONMENTS                  │
        │                                                         │
        │  ┌──────────────────┐  ┌─────────────────────────────┐ │
        │  │ LOCAL DEPLOYMENT │  │    SERVER DEPLOYMENT        │ │
        │  │                  │  │                             │ │
        │  │ ┌──────────────┐ │  │ ┌─────────────────────────┐ │ │
        │  │ │ Message Bus  │ │  │ │   FastAPI Server        │ │ │
        │  │ │ (InMemory/   │ │  │ │   (Port-based)          │ │ │
        │  │ │ Redis)       │ │  │ └─────────────────────────┘ │ │
        │  │ └──────────────┘ │  │                             │ │
        │  │                  │  │ ┌─────────────────────────┐ │ │
        │  │ ┌──────────────┐ │  │ │   HTTP API Routing      │ │ │
        │  │ │ Components   │ │  │ │   (Component Access)    │ │ │
        │  │ │ (Direct)     │ │  │ └─────────────────────────┘ │ │
        │  │ └──────────────┘ │  └─────────────────────────────┘ │
        │  └──────────────────┘                                  │
        │                                                         │
        │  ┌─────────────────────────────────────────────────┐   │
        │  │           DOCKER DEPLOYMENT                     │   │
        │  │                                                 │   │
        │  │ ┌─────────────────┐ ┌─────────────────────────┐ │   │
        │  │ │   Container 1   │ │     Container 2         │ │   │
        │  │ │                 │ │                         │ │   │
        │  │ │ ┌─────────────┐ │ │ ┌─────────────────────┐ │ │   │
        │  │ │ │ Component   │ │ │ │   Message Bus       │ │ │   │
        │  │ │ │ Process     │ │ │ │   (Redis/NATS)      │ │ │   │
        │  │ │ └─────────────┘ │ │ └─────────────────────┘ │ │   │
        │  │ │                 │ │                         │ │   │
        │  │ │ ┌─────────────┐ │ │ ┌─────────────────────┐ │ │   │
        │  │ │ │ Volume      │ │ │ │   Service           │ │ │   │
        │  │ │ │ Mounts      │ │ │ │   Discovery         │ │ │   │
        │  │ │ └─────────────┘ │ │ └─────────────────────┘ │ │   │
        │  │ └─────────────────┘ └─────────────────────────┘ │   │
        │  └─────────────────────────────────────────────────┘   │
        └─────────────────────────────────────────────────────────┘
```

### Phase-Based Startup Sequence (Aligned with Existing Architecture)

#### Phase 1: Sync Configuration (Main Process) - **Building on Existing**
```python
# main.py - Enhanced version of existing app_entrypoint
def app_entrypoint(args):
    # 1. Parse configuration (existing sync parser)
    config = config_parser.parse(config_file)

    # 2. Initialize deployment registry (existing)
    registry = get_registry()
    deployer = Deployer()

    # 3. NEW: Create distributed startup coordinator
    coordinator = DistributedStartupCoordinator(config, registry, deployer)

    # 4. Hand off to coordinator (replaces existing startup logic)
    coordinator.coordinate_distributed_startup()
```

#### Phase 2: Deployment-Aware Startup (Building on Existing Router)
```python
class DistributedStartupCoordinator:
    def __init__(self, config, registry, deployer):
        self.config = config
        self.registry = registry
        self.deployer = deployer
        self.router = get_router()  # Existing deployment router

    def coordinate_distributed_startup(self):
        # 1. Analyze deployment requirements from config
        deployment_types = self._analyze_deployments()

        # 2. Route to appropriate startup strategy
        if 'docker' in deployment_types:
            self._start_containerized_mode()
        elif 'server' in deployment_types:
            self._start_server_mode()
        else:
            self._start_local_distributed_mode()

    def _start_containerized_mode(self):
        """Docker deployment with message bus"""
        # 1. Build Docker containers (existing Docker class)
        containers = self._build_containers()

        # 2. Start message bus container first
        message_bus_container = self._start_message_bus_container()

        # 3. Start component containers with message bus connection
        component_containers = self._start_component_containers(message_bus_container)

        # 4. Setup service discovery and health monitoring
        self._setup_container_coordination()

    def _start_server_mode(self):
        """FastAPI server deployment with distributed coordination"""
        # 1. Setup message bus (Redis for multi-server)
        message_bus = self._setup_distributed_message_bus()

        # 2. Start FastAPI servers (existing ServerDeployment)
        servers = self._start_server_deployments()

        # 3. Register servers with message bus for coordination
        self._register_servers_with_message_bus(servers, message_bus)

    def _start_local_distributed_mode(self):
        """Local development with distributed message bus (InMemory/Redis)"""
        # 1. Start message bus in dedicated thread (NOT process for simplicity)
        message_bus_thread = self._start_message_bus_thread()

        # 2. Initialize components with message bus integration
        components = self._initialize_components_with_message_bus()

        # 3. Start main event loop (existing message bus loop)
        self._start_message_bus_main_loop(components)
```

#### Phase 3: Container-Based Message Bus (New for Docker)
```python
def create_message_bus_container():
    """Create dedicated message bus container using existing Docker class"""

    # Use existing Docker class with Redis image
    docker_config = Docker(
        image_name="redis:alpine",
        container_name="woodwork-message-bus",
        dockerfile=None,  # Use pre-built image
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
    return docker_config.get_container()

def create_component_container(component_config, message_bus_container):
    """Create component container connected to message bus"""

    # Generate Dockerfile for component
    dockerfile = f"""
    FROM python:3.11-slim
    COPY requirements.txt .
    RUN pip install -r requirements.txt
    COPY . /app
    WORKDIR /app
    ENV WOODWORK_MESSAGE_BUS=redis://message-bus:6379
    CMD ["python", "-m", "woodwork", "component", "{component_config['name']}"]
    """

    docker_config = Docker(
        image_name=f"woodwork-{component_config['name']}",
        container_name=f"woodwork-{component_config['name']}",
        dockerfile=dockerfile,
        container_args={
            "links": {message_bus_container.name: "message-bus"},
            "environment": {
                "COMPONENT_CONFIG": json.dumps(component_config)
            }
        }
    )

    docker_config.init()
    return docker_config.get_container()
```

#### Phase 4: Server Deployment Integration (Enhanced Existing)
```python
class DistributedServerDeployment(ServerDeployment):
    """Enhanced ServerDeployment with message bus integration"""

    def __init__(self, components, port=43001, message_bus_url=None, **config):
        super().__init__(components, port, **config)
        self.message_bus_url = message_bus_url or "redis://localhost:6379"
        self._setup_distributed_integration()

    def _setup_distributed_integration(self):
        """Setup message bus integration for server deployment"""

        # Add health check endpoint
        @self.app.get("/health")
        async def health_check():
            # Check message bus connectivity
            bus_health = await self._check_message_bus_health()
            return {"status": "healthy", "message_bus": bus_health}

        # Add component discovery endpoint
        @self.app.get("/components")
        async def list_components():
            return [{"name": comp.name, "type": comp.type} for comp in self.components]

        # Enhanced component routes with message bus coordination
        for comp in self.components:
            @self.app.post(f"/{comp.name}/input")
            async def enhanced_input(request: Request):
                data = await request.json()

                # Process through component
                result = await self._maybe_async(comp.input, data["value"])

                # Emit through message bus for coordination
                await self._emit_to_message_bus("component.output", {
                    "component": comp.name,
                    "result": result,
                    "server": self.port
                })

                return result

    async def deploy(self):
        # 1. Connect to message bus first
        await self._connect_to_message_bus()

        # 2. Start FastAPI server (existing)
        await super().deploy()
```

#### Phase 5: Local Development (Enhanced Existing)
```python
def enhanced_start_message_bus_loop(tools):
    """Enhanced version of existing start_message_bus_loop with proper threading"""

    def run_message_bus_background():
        """Background thread specifically for message bus event loop"""
        # Create dedicated event loop for message bus
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def message_bus_runtime():
            # 1. Start message bus (existing integration.py approach)
            from woodwork.core.message_bus.factory import get_global_message_bus
            message_bus = await get_global_message_bus()
            log.info("✅ Message bus started with background tasks")

            # 2. Setup component integration (existing approach)
            from woodwork.core.message_bus.integration import get_global_message_bus_manager
            manager = get_global_message_bus_manager()

            # 3. Setup streaming (existing Router.setup_streaming)
            router = get_router()
            stream_manager = await router.setup_streaming()

            # 4. Start main loop (existing message_bus_main_loop)
            input_components = [tool for tool in tools if isinstance(tool, inputs)]
            if input_components:
                await message_bus_main_loop(input_components[0])

        # Run in dedicated thread with proper cleanup
        try:
            loop.run_until_complete(message_bus_runtime())
        except KeyboardInterrupt:
            log.info("Message bus thread shutting down...")
        finally:
            loop.close()

    # Start in daemon thread (allows main process to exit cleanly)
    import threading
    message_bus_thread = threading.Thread(target=run_message_bus_background, daemon=True)
    message_bus_thread.start()

    # Keep main thread alive for CLI interaction
    try:
        message_bus_thread.join()
    except KeyboardInterrupt:
        log.info("Shutting down distributed system...")
```

### GIL-Aware Resource Allocation

#### CPU-Bound Tasks → Multiprocessing
- Component initialization (LLM loading, DB connections)
- Heavy computation (embeddings, model inference)
- File I/O for large knowledge bases

#### I/O-Bound Tasks → Threading
- Network requests (OpenAI API, web scraping)
- Message bus communication
- User input/output handling
- Streaming operations

#### Async Tasks → Single Event Loop (Message Bus Process)
- Message routing and delivery
- Retry logic and exponential backoff
- Connection pooling and health checks
- Inter-component coordination

### Memory Safety & Resource Management

#### Process Isolation
```python
class ProcessPool:
    def __init__(self, max_workers=4):
        self.processes = {}
        self.shared_memory = multiprocessing.Manager()
        self.message_queues = {}

    def start_component_worker(self, component_config):
        # Isolated process for each component type
        queue = multiprocessing.Queue()
        process = multiprocessing.Process(
            target=component_worker_main,
            args=(component_config, queue)
        )
        process.start()
        return process, queue
```

#### Clean Shutdown Protocol
```python
class ShutdownCoordinator:
    async def shutdown_distributed_system(self):
        # 1. Stop accepting new work
        await self.message_bus.stop_accepting()

        # 2. Drain message queues
        await self.message_bus.drain_queues()

        # 3. Shutdown component workers
        await self.shutdown_component_workers()

        # 4. Shutdown message bus
        await self.message_bus.stop()

        # 5. Cleanup resources
        self.cleanup_shared_resources()
```

## Implementation Strategy

### Phase 1: Minimal Viable Fix (Immediate)
1. **Fix Event Loop Ownership**: Make message bus process own its event loop
2. **Separate Startup from Runtime**: Clean handoff between sync config and async runtime
3. **Fix Resource Leaks**: Proper cleanup of threads and processes

### Phase 2: Clean Architecture (Near-term)
1. **Startup Coordinator**: Central orchestration of startup sequence
2. **Process Separation**: Dedicated message bus process
3. **Worker Pool**: Multiprocess component workers

### Phase 3: Performance Optimization (Long-term)
1. **Smart Scheduling**: CPU vs I/O bound task allocation
2. **Resource Monitoring**: Memory and CPU usage tracking
3. **Auto-scaling**: Dynamic worker pool sizing

## Benefits of This Architecture

### 1. **Clean Separation of Concerns**
- Sync startup logic stays sync
- Async runtime logic stays async
- No impedance mismatch

### 2. **GIL Optimization**
- CPU work in separate processes (no GIL)
- I/O work in threads (GIL released during I/O)
- Async coordination in dedicated process

### 3. **Memory Safety**
- Process isolation prevents memory leaks
- Clear resource ownership
- Graceful shutdown protocol

### 4. **Scalability**
- Worker processes can scale independently
- Message bus can be swapped for Redis/NATS
- I/O threads scale with connections

### 5. **Debuggability**
- Clear process boundaries
- Isolated failure domains
- Proper logging and monitoring

## Migration Path (Aligned with Existing Implementation)

### Step 1: Fix Current Issues (Immediate - This Week)
```python
# Enhanced version of existing start_message_bus_loop with proper threading
def enhanced_start_message_bus_loop(tools):
    """Fix retry processor task death by using dedicated thread with event loop"""

    def run_message_bus_background():
        # Dedicated event loop in separate thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def message_bus_runtime():
            # Use existing integration approach
            from woodwork.core.message_bus.factory import get_global_message_bus
            message_bus = await get_global_message_bus()  # This starts retry processor

            # Existing streaming setup
            router = get_router()
            stream_manager = await router.setup_streaming()

            # Existing main loop
            input_components = [tool for tool in tools if isinstance(tool, inputs)]
            if input_components:
                await message_bus_main_loop(input_components[0])

        loop.run_until_complete(message_bus_runtime())

    # Daemon thread for clean shutdown
    threading.Thread(target=run_message_bus_background, daemon=True).start()
```

### Step 2: Deployment Integration (Next Sprint)
```python
# Add DistributedStartupCoordinator to existing main.py
class DistributedStartupCoordinator:
    def __init__(self, config, registry, deployer):
        self.config = config
        self.registry = registry
        self.deployer = deployer
        self.router = get_router()  # Use existing router

    def coordinate_distributed_startup(self):
        # Analyze existing deployment configuration
        deployment_configs = self._extract_deployment_configs()

        # Route based on existing deployment types
        for deploy_config in deployment_configs:
            if deploy_config.get('type') == 'docker':
                self._enhance_docker_deployment(deploy_config)
            elif deploy_config.get('type') == 'server':
                self._enhance_server_deployment(deploy_config)
            else:
                self._enhance_local_deployment(deploy_config)

# Integration point in existing app_entrypoint
def app_entrypoint(args):
    # ... existing configuration logic ...

    # NEW: Add distributed coordination
    coordinator = DistributedStartupCoordinator(commands, registry, deployer)
    coordinator.coordinate_distributed_startup()

    # Replace existing start_message_bus_loop call
    enhanced_start_message_bus_loop(config_parser.task_m._tools)
```

### Step 3: Docker Enhancement (Future)
```python
# Enhance existing Docker class with message bus support
class DistributedDockerDeployment:
    def __init__(self, components, message_bus_config=None, **config):
        self.components = components
        self.message_bus_config = message_bus_config or {"type": "redis"}

        # Create message bus container using existing Docker class
        self.message_bus_docker = Docker(
            image_name="redis:alpine",
            container_name="woodwork-message-bus",
            dockerfile=None,
            container_args={"ports": {"6379": "6379"}}
        )

        # Create component containers
        self.component_dockers = []
        for component in components:
            component_docker = self._create_component_container(component)
            self.component_dockers.append(component_docker)

    def deploy(self):
        # 1. Start message bus container
        self.message_bus_docker.init()

        # 2. Start component containers with message bus connection
        for component_docker in self.component_dockers:
            component_docker.init()

# Integration with existing deployment system
def create_object(command):
    # ... existing component creation logic ...

    # Enhanced VM deployment with distributed support
    if component == "vm":
        if type == "distributed_server":
            return DistributedServerDeployment(**config)
        elif type == "distributed_docker":
            return DistributedDockerDeployment(**config)
        elif type == "server":
            # Enhance existing ServerDeployment
            return EnhancedServerDeployment(**config)
```

### Step 4: Production Features (Long-term)
- Redis/NATS message bus backends for true distributed operation
- Component registry and service discovery
- Circuit breakers and health monitoring
- Auto-scaling and load balancing

## Key Insights from Existing Architecture Analysis

### What's Already Working ✅

1. **Distributed Message Bus System**: Fully implemented with InMemoryMessageBus, declarative routing, and seamless event system integration
2. **Deployment Infrastructure**: Docker, ServerDeployment, and LocalDeployment classes provide solid foundation
3. **Component Registry**: Existing registry system can be enhanced for service discovery
4. **Configuration Parser**: Already handles complex .ww configurations with dependency resolution

### What Needs Enhancement 🔧

1. **Startup Coordination**: Current startup is sequential and synchronous - needs distributed coordination
2. **Event Loop Management**: Retry processor task death issue due to cross-thread event loop problems
3. **Docker Integration**: Existing Docker class needs message bus connectivity and multi-container coordination
4. **Server Deployment**: FastAPI servers need message bus integration for distributed coordination

### Aligned Implementation Strategy 🎯

#### Immediate (This Week): Fix Event Loop Issues
- Use dedicated thread for message bus with proper event loop ownership
- Build on existing `start_message_bus_loop` function
- Maintain existing component initialization approach

#### Short-term (Next Sprint): Enhance Existing Deployments
- Add `DistributedStartupCoordinator` that works with existing `Deployer` and `Router`
- Enhance `Docker` class with message bus container support
- Extend `ServerDeployment` with distributed coordination endpoints

#### Medium-term: Production Distributed Features
- Redis/NATS backends using existing `MessageBusFactory` approach
- Component registry using existing registry infrastructure
- Docker compose integration for multi-container deployments

## Benefits of This Aligned Approach

1. **Preserves Existing Investments**: Builds on proven Docker, FastAPI, and deployment infrastructure
2. **Incremental Migration**: Can deploy step-by-step without breaking existing functionality
3. **Familiar Patterns**: Uses existing Router, Registry, and Deployer patterns users understand
4. **Production Ready**: Leverages existing Docker and server deployment capabilities for real production use

## Configuration Examples (Aligned with Existing .ww Syntax)

### Enhanced Local Development
```python
# main.ww - Works with existing parser
deployment = local {
    message_bus = redis {
        redis_url = $REDIS_URL
    }
}

agent = claude {
    model = "claude-3-sonnet"
    to = ["output", "metrics"]  # Existing routing syntax
}
```

### Enhanced Docker Deployment
```python
# main.ww - Builds on existing Docker integration
deployment = docker {
    message_bus = redis {
        image = "redis:alpine"
        ports = { "6379": "6379" }
    }

    components = {
        agent_container = {
            image = "woodwork-agent"
            environment = {
                "COMPONENT_TYPE" = "agent"
                "MESSAGE_BUS_URL" = "redis://message-bus:6379"
            }
        }
    }
}
```

### Enhanced Server Deployment
```python
# main.ww - Extends existing ServerDeployment
deployment = server {
    port = 8080
    message_bus = "redis://cluster:6379"

    health_checks = true
    component_discovery = true
}
```

The goal is a **clean, distributed, and production-ready** architecture that **builds on existing strengths** while solving the fundamental startup and event loop coordination issues that are blocking distributed operation.