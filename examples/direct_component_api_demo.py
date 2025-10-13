"""
Demo: Direct Component Creation API vs Feature System

This demonstrates two approaches to adding components to agents:
1. Direct API: agent.create_component(...)
2. Feature System: my_feature: true in config
"""

# Approach 1: Direct Component Creation API
class DirectComponentAgent:
    """Agent with direct component creation API."""

    def __init__(self, **config):
        self._internal_component_manager = InternalComponentManager()

    def create_component(self, component_type: str, component_id: str = None, **config):
        """Direct API to create and attach internal components."""
        component_id = component_id or f"{self.name}_{component_type}_{len(self._internal_component_manager._components)}"

        # Create component through internal manager
        component = self._internal_component_manager.get_or_create_component(
            component_id, component_type, config
        )

        # Auto-attach to agent
        setattr(self, f"_{component_type}", component)

        return component

    def add_hook(self, event_name: str, hook_function):
        """Add hook to this agent."""
        from woodwork.core.unified_event_bus import get_global_event_bus
        event_bus = get_global_event_bus()
        event_bus.register_hook(event_name, hook_function)

    def add_pipe(self, event_name: str, pipe_function):
        """Add pipe to this agent."""
        from woodwork.core.unified_event_bus import get_global_event_bus
        event_bus = get_global_event_bus()
        event_bus.register_pipe(event_name, pipe_function)

# Usage Examples:

# Approach 1: Direct API (Imperative)
def setup_agent_direct_api():
    """Direct API approach - more code, more control."""
    agent = DirectComponentAgent(name="my_agent")

    # Create Neo4j component directly
    neo4j = agent.create_component(
        "neo4j",
        uri="bolt://localhost:7687",
        user="neo4j",
        password="testpassword",
        api_key="my-api-key"
    )

    # Add hooks manually
    def capture_thoughts(payload):
        neo4j.create_node("Thought", {"text": payload.thought})

    def enhance_input(payload):
        results = neo4j.similarity_search(payload.input)
        if results:
            enhanced = f"{payload.input}\n\nContext: {results[0]['text']}"
            return payload._replace(input=enhanced)
        return payload

    agent.add_hook("agent.thought", capture_thoughts)
    agent.add_pipe("input.received", enhance_input)

    # Create Redis component
    redis = agent.create_component(
        "redis",
        host="localhost",
        port=6379,
        db=0
    )

    # Add Redis caching hook
    def cache_actions(payload):
        redis.set(f"action:{payload.component_id}", payload.action)

    agent.add_hook("agent.action", cache_actions)

    return agent

# Approach 2: Feature System (Declarative)
def setup_agent_feature_system():
    """Feature system approach - less code, standardized patterns."""

    # Just config - everything else is automatic
    config = {
        "name": "my_agent",
        "knowledge_graph": True,  # Auto-creates Neo4j + hooks/pipes
        "action_cache": True,     # Auto-creates Redis + caching hooks
        "custom_analytics": True  # Auto-creates analytics pipeline
    }

    # All components, hooks, and pipes created automatically
    agent = Agent(**config)

    return agent

print("=== COMPARISON ===")

print("\n🔧 DIRECT API APPROACH:")
print("✅ More control over component configuration")
print("✅ Dynamic component creation at runtime")
print("✅ Custom hook/pipe logic per instance")
print("✅ No need to pre-define features")
print("❌ More verbose code")
print("❌ Manual lifecycle management")
print("❌ Easy to forget hooks/pipes")
print("❌ Harder to standardize patterns")

print("\n🏗️ FEATURE SYSTEM APPROACH:")
print("✅ Extremely concise (one line in config)")
print("✅ Automatic lifecycle management")
print("✅ Standardized, tested patterns")
print("✅ Reusable across projects")
print("✅ Automatic hook/pipe registration")
print("❌ Less runtime flexibility")
print("❌ Need to pre-define features")
print("❌ Less granular control")

print("\n💡 RECOMMENDATION:")
print("Use Feature System for common patterns (knowledge graphs, caching, monitoring)")
print("Use Direct API for one-off customizations or dynamic scenarios")
print("They can work together in the same agent!")