"""
Demo: Using Direct API in __init__ for Startup Component Creation

This shows how you can use the direct API in component __init__ methods
to create components and register hooks/pipes at startup time.
"""

from woodwork.components.agents.llm import llm as base_llm
from woodwork.components.component import component
import logging

log = logging.getLogger(__name__)

class IntelligentAgent(base_llm):
    """Agent that uses direct API in __init__ to set up components and hooks/pipes."""

    def __init__(self, model, **config):
        # Call parent constructor first
        super().__init__(model, **config)

        # 🚀 USE DIRECT API IN __init__ FOR STARTUP SETUP!
        self._setup_startup_components(config)
        self._setup_startup_hooks()
        self._setup_startup_pipes()

        log.info(f"IntelligentAgent '{self.name}' fully initialized with startup components")

    def _setup_startup_components(self, config):
        """Create components at startup using direct API."""

        # Create knowledge graph for intelligent reasoning
        if config.get("enable_knowledge", True):
            try:
                self.knowledge_db = self.create_component(
                    "neo4j",
                    component_id="knowledge_graph",
                    uri="bolt://localhost:7687",
                    user="neo4j",
                    password="agentpassword",
                    name=f"{self.name}_knowledge"
                )
                log.info(f"Agent '{self.name}' created knowledge graph at startup")
            except Exception as e:
                log.warning(f"Could not create knowledge graph: {e}")

        # Create memory cache for fast retrieval
        if config.get("enable_cache", True):
            try:
                self.memory_cache = self.create_component(
                    "redis",
                    component_id="memory_cache",
                    host="localhost",
                    port=6379,
                    db=1  # Use DB 1 for agent memory
                )
                log.info(f"Agent '{self.name}' created memory cache at startup")
            except Exception as e:
                log.warning(f"Could not create memory cache: {e}")

        # Create analytics tracker
        if config.get("enable_analytics", False):
            try:
                self.analytics = self.create_component(
                    "elasticsearch",
                    component_id="analytics_tracker",
                    host="localhost",
                    port=9200,
                    index=f"{self.name}_analytics"
                )
                log.info(f"Agent '{self.name}' created analytics tracker at startup")
            except Exception as e:
                log.warning(f"Could not create analytics: {e}")

    def _setup_startup_hooks(self):
        """Register hooks at startup using direct API."""

        # Hook to capture and store all thoughts in knowledge graph
        def store_thought_in_knowledge(payload):
            if hasattr(self, 'knowledge_db') and hasattr(payload, 'thought'):
                try:
                    self.knowledge_db.create_node("Thought", {
                        "text": payload.thought,
                        "agent": self.name,
                        "timestamp": payload.get('timestamp', 'unknown')
                    })
                    log.debug(f"Stored thought in knowledge graph: {payload.thought[:50]}...")
                except Exception as e:
                    log.debug(f"Failed to store thought: {e}")

        self.add_hook("agent.thought", store_thought_in_knowledge, "Store thoughts in knowledge graph")

        # Hook to cache successful actions in Redis
        def cache_successful_action(payload):
            if hasattr(self, 'memory_cache') and hasattr(payload, 'action'):
                try:
                    action_key = f"action:{hash(str(payload.action))}"
                    self.memory_cache.setex(action_key, 3600, str(payload.action))  # Cache for 1 hour
                    log.debug(f"Cached action: {payload.action}")
                except Exception as e:
                    log.debug(f"Failed to cache action: {e}")

        self.add_hook("agent.action", cache_successful_action, "Cache actions in Redis")

        # Hook to track analytics
        def track_agent_analytics(payload):
            if hasattr(self, 'analytics'):
                try:
                    self.analytics.index({
                        "event": "step_complete",
                        "agent": self.name,
                        "step": payload.get('step', 0),
                        "session": payload.get('session_id', 'unknown'),
                        "timestamp": payload.get('timestamp', 'unknown')
                    })
                    log.debug(f"Tracked analytics for step {payload.get('step', 0)}")
                except Exception as e:
                    log.debug(f"Failed to track analytics: {e}")

        self.add_hook("agent.step_complete", track_agent_analytics, "Track agent analytics")

    def _setup_startup_pipes(self):
        """Register pipes at startup using direct API."""

        # Pipe to enhance input with knowledge from graph
        def enhance_with_knowledge(payload):
            if hasattr(self, 'knowledge_db') and hasattr(payload, 'input'):
                try:
                    # Search for relevant knowledge
                    relevant = self.knowledge_db.similarity_search(payload.input, limit=3)
                    if relevant and len(relevant) > 0:
                        knowledge_text = "\n".join([f"- {item.get('text', '')}" for item in relevant[:2]])
                        enhanced_input = f"{payload.input}\n\n[Knowledge Context]:\n{knowledge_text}"

                        # Return modified payload
                        return payload._replace(input=enhanced_input)

                except Exception as e:
                    log.debug(f"Failed to enhance with knowledge: {e}")

            return payload  # Return unmodified if enhancement fails

        self.add_pipe("input.received", enhance_with_knowledge, "Enhance input with graph knowledge")

        # Pipe to check cache for similar inputs
        def check_action_cache(payload):
            if hasattr(self, 'memory_cache') and hasattr(payload, 'input'):
                try:
                    # Check if we've seen similar input before
                    input_hash = hash(payload.input.lower().strip())
                    cached_action = self.memory_cache.get(f"input:{input_hash}")

                    if cached_action:
                        log.debug(f"Found cached action for similar input")
                        # Could add cache hit indicator to payload
                        enhanced_payload = payload._replace(
                            input=f"{payload.input}\n\n[Cache Hint]: Similar to previous successful action"
                        )
                        return enhanced_payload

                except Exception as e:
                    log.debug(f"Failed to check cache: {e}")

            return payload

        self.add_pipe("input.received", check_action_cache, "Check cache for similar inputs")


class SmartTool(component):
    """Example tool that sets up monitoring at startup."""

    def __init__(self, name, component, type, **config):
        super().__init__(name, component, type, **config)

        # 🚀 TOOLS CAN ALSO USE DIRECT API AT STARTUP!
        self._setup_tool_monitoring()

    def _setup_tool_monitoring(self):
        """Set up monitoring hooks for this tool."""

        # Track how often this tool is called
        self.call_count = 0

        def track_tool_usage(payload):
            if hasattr(payload, 'tool') and payload.tool == self.name:
                self.call_count += 1
                log.info(f"Tool '{self.name}' has been called {self.call_count} times")

        self.add_hook("tool.call", track_tool_usage, f"Track usage of {self.name}")

        # Add context to tool observations
        def add_tool_context(payload):
            if hasattr(payload, 'tool') and payload.tool == self.name:
                enhanced_obs = f"[{self.name}] {payload.observation}"
                return payload._replace(observation=enhanced_obs)
            return payload

        self.add_pipe("tool.observation", add_tool_context, f"Add context from {self.name}")


# Usage Examples:

def example_agent_with_startup_components():
    """Example of agent that sets up everything at startup."""

    # Mock LLM model
    class MockLLM:
        def __init__(self):
            self._api_key = "test-key"
            self._llm = self  # Mock for demo

    # Mock task master and tools
    class MockTaskMaster:
        def start_workflow(self, query): pass
        def end_workflow(self): pass

    # Create agent - all components and hooks/pipes set up automatically!
    agent = IntelligentAgent(
        model=MockLLM(),
        tools=[],  # Required parameter
        task_m=MockTaskMaster(),  # Required parameter
        name="smart_agent",
        component="llm",
        type="agent",
        enable_knowledge=True,   # Creates Neo4j + knowledge hooks/pipes
        enable_cache=True,       # Creates Redis + caching hooks/pipes
        enable_analytics=True    # Creates Elasticsearch + analytics hooks
    )

    print("✅ Agent created with startup components:")
    print(f"  - Knowledge DB: {hasattr(agent, 'knowledge_db')}")
    print(f"  - Memory Cache: {hasattr(agent, 'memory_cache')}")
    print(f"  - Analytics: {hasattr(agent, 'analytics')}")
    print(f"  - Hooks registered automatically at startup")
    print(f"  - Pipes registered automatically at startup")

    return agent


def example_tool_with_startup_monitoring():
    """Example of tool that sets up monitoring at startup."""

    # Create tool - monitoring set up automatically!
    tool = SmartTool(
        name="data_analyzer",
        component="tool",
        type="analysis"
    )

    print("✅ Tool created with startup monitoring:")
    print(f"  - Call tracking: Ready")
    print(f"  - Context enhancement: Ready")
    print(f"  - Hooks registered automatically at startup")

    return tool


if __name__ == "__main__":
    print("🚀 DIRECT API IN __init__ DEMO")
    print("=" * 50)

    print("\n1️⃣ Agent with Startup Components:")
    agent = example_agent_with_startup_components()

    print("\n2️⃣ Tool with Startup Monitoring:")
    tool = example_tool_with_startup_monitoring()

    print("\n✨ KEY BENEFITS:")
    print("✅ Components created automatically at startup")
    print("✅ Hooks and pipes registered immediately")
    print("✅ No config needed - just enable flags")
    print("✅ Works with ANY component type")
    print("✅ Declarative AND programmatic")
    print("✅ Full control over startup behavior")

    print("\n🎯 COMPARISON:")
    print("Feature System:  my_feature: true  (external config)")
    print("Direct API Init: self.setup_x()    (internal code)")
    print("Both work perfectly together! 🎉")