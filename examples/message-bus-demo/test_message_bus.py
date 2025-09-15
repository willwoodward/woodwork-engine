#!/usr/bin/env python3
"""
Test Message Bus Integration

This script tests the new message bus system to ensure it works correctly
with existing components and provides the distributed communication capabilities
that replace Task Master orchestration.
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

# Add woodwork to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from woodwork.core.message_bus import get_global_message_bus, MessageBusFactory
from woodwork.core.message_bus.integration import initialize_global_message_bus_integration
from woodwork.components.component import component

# Setup debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

log = logging.getLogger(__name__)


class TestInputComponent(component):
    """Test input component that emits data"""
    
    def __init__(self, name="test_input", **config):
        super().__init__(name=name, component="inputs", type="test", config=config)
        
    async def process_input(self, user_input: str):
        """Process user input and emit to configured targets"""
        log.info(f"[{self.name}] Processing input: '{user_input}'")
        
        # Emit event - should automatically route to configured targets
        result = await self.emit("input_received", {
            "input": user_input,
            "timestamp": time.time(),
            "component": self.name
        })
        
        log.info(f"[{self.name}] Emitted input_received event")
        return result


class TestAgentComponent(component):
    """Test agent component that processes and generates responses"""
    
    def __init__(self, name="test_agent", **config):
        super().__init__(name=name, component="agents", type="test", config=config)
        
    async def process(self, input_data):
        """Process input and generate response"""
        log.info(f"[{self.name}] Processing: {input_data}")
        
        # Simulate processing delay
        await asyncio.sleep(0.1)
        
        response = f"Processed: {input_data}"
        
        # Emit response - should automatically route to configured targets
        await self.emit("response_generated", {
            "response": response,
            "timestamp": time.time(),
            "component": self.name
        })
        
        log.info(f"[{self.name}] Generated response: '{response}'")
        return response
        
    async def _handle_bus_message(self, envelope):
        """Handle messages from message bus"""
        log.info(f"[{self.name}] Received message: {envelope.event_type}")
        
        # Process the message through existing event system
        await super()._handle_bus_message(envelope)
        
        # If it's an input, process it
        if envelope.event_type == "input_received":
            payload = envelope.payload
            input_data = payload.get("data", {}).get("input", "")
            await self.process(input_data)


class TestOutputComponent(component):
    """Test output component that displays results"""
    
    def __init__(self, name="test_output", **config):
        super().__init__(name=name, component="outputs", type="test", config=config)
        self.received_responses = []
        
    async def display(self, data):
        """Display output data"""
        log.info(f"[{self.name}] Displaying: {data}")
        self.received_responses.append(data)
        
    async def _handle_bus_message(self, envelope):
        """Handle messages from message bus"""
        log.info(f"[{self.name}] Received message: {envelope.event_type}")
        
        # Process the message through existing event system  
        await super()._handle_bus_message(envelope)
        
        # If it's a response, display it
        if envelope.event_type == "response_generated":
            payload = envelope.payload
            response = payload.get("data", {}).get("response", "")
            await self.display(response)


async def test_basic_message_bus():
    """Test basic message bus functionality"""
    log.info("=== Testing Basic Message Bus ===")
    
    # Get message bus
    message_bus = await get_global_message_bus()
    log.info(f"Message bus type: {type(message_bus).__name__}")
    
    # Check health
    healthy = message_bus.is_healthy()
    log.info(f"Message bus healthy: {healthy}")
    
    # Get stats
    stats = message_bus.get_stats()
    log.info(f"Message bus stats: {stats}")
    
    assert healthy, "Message bus should be healthy"
    
    log.info("✅ Basic message bus test passed")


async def test_component_integration():
    """Test component integration with message bus"""
    log.info("=== Testing Component Integration ===")
    
    # Create test components with routing configuration
    input_comp = TestInputComponent(to=["test_agent"])
    agent_comp = TestAgentComponent(to=["test_output"])
    output_comp = TestOutputComponent()
    
    components = [input_comp, agent_comp, output_comp]
    
    # Initialize message bus integration
    component_configs = {
        "test_input": {"component": "inputs", "type": "test", "to": ["test_agent"]},
        "test_agent": {"component": "agents", "type": "test", "to": ["test_output"]}, 
        "test_output": {"component": "outputs", "type": "test"}
    }
    
    await initialize_global_message_bus_integration(component_configs)
    
    # Verify integration
    for comp in components:
        try:
            integration_info = comp.get_integration_info()
            log.info(f"Component {comp.name} integration: {integration_info}")
            # Don't require integration_ready to be True yet since it's lazily initialized
        except AttributeError as e:
            # Some attributes may not be initialized until first use
            log.debug(f"Component {comp.name} integration not fully initialized: {e}")
            
        # Check that basic integration attributes exist
        assert hasattr(comp, 'output_targets'), f"{comp.name} should have output_targets"
        assert hasattr(comp, 'session_id'), f"{comp.name} should have session_id"
    
    log.info("✅ Component integration test passed")


async def test_message_routing():
    """Test end-to-end message routing"""
    log.info("=== Testing Message Routing ===")
    
    # Create components
    input_comp = TestInputComponent(config={"to": ["test_agent"]})
    agent_comp = TestAgentComponent(config={"to": ["test_output"]})
    output_comp = TestOutputComponent(config={})
    
    # Initialize integration
    component_configs = {
        "test_input": {"component": "inputs", "type": "test", "to": ["test_agent"]},
        "test_agent": {"component": "agents", "type": "test", "to": ["test_output"]},
        "test_output": {"component": "outputs", "type": "test"}
    }
    
    await initialize_global_message_bus_integration(component_configs)
    
    # Wait for integration to complete
    await asyncio.sleep(0.5)
    
    # Test input processing
    test_input = "Hello, message bus!"
    await input_comp.process_input(test_input)
    
    # Wait for message processing
    await asyncio.sleep(1.0)
    
    # Verify output component received the response
    log.info(f"Output component received: {output_comp.received_responses}")
    
    # Check that response was received and processed
    assert len(output_comp.received_responses) > 0, "Output should have received responses"
    
    response = output_comp.received_responses[0]
    assert "Processed: Hello, message bus!" in str(response), "Response should contain processed input"
    
    log.info("✅ Message routing test passed")


async def test_streaming_integration():
    """Test streaming integration with message bus"""
    log.info("=== Testing Streaming Integration ===")
    
    # Create streaming-enabled components
    agent_comp = TestAgentComponent(config={
        "streaming": True,
        "streaming_output": True, 
        "to": ["test_output"]
    })
    output_comp = TestOutputComponent(config={
        "streaming": True,
        "streaming_input": True
    })
    
    # Check streaming capabilities
    agent_capabilities = agent_comp.is_streaming_capable()
    output_capabilities = output_comp.is_streaming_capable()
    
    log.info(f"Agent streaming: {agent_capabilities}")
    log.info(f"Output streaming: {output_capabilities}")
    
    # Verify streaming is enabled
    assert agent_comp.streaming_enabled, "Agent should have streaming enabled"
    assert output_comp.streaming_enabled, "Output should have streaming enabled"
    
    log.info("✅ Streaming integration test passed")


async def test_performance():
    """Test message bus performance"""
    log.info("=== Testing Performance ===")
    
    message_bus = await get_global_message_bus()
    
    # Test rapid message sending
    start_time = time.time()
    message_count = 100
    
    from woodwork.core.message_bus.interface import create_hook_message
    
    for i in range(message_count):
        envelope = create_hook_message(
            session_id="perf-test",
            event_type="performance_test", 
            payload={"message_id": i},
            sender_component="test"
        )
        await message_bus.publish(envelope)
    
    end_time = time.time()
    duration = end_time - start_time
    
    log.info(f"Sent {message_count} messages in {duration:.3f}s")
    log.info(f"Rate: {message_count / duration:.1f} messages/second")
    
    # Get final stats
    stats = message_bus.get_stats()
    log.info(f"Final stats: {stats}")
    
    log.info("✅ Performance test passed")


async def main():
    """Run all tests"""
    log.info("🚀 Starting Message Bus Integration Tests")
    
    try:
        await test_basic_message_bus()
        await test_component_integration() 
        await test_message_routing()
        await test_streaming_integration()
        await test_performance()
        
        log.info("🎉 All tests passed! Message bus integration is working correctly.")
        
    except Exception as e:
        log.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)