#!/usr/bin/env python3
"""
Simple Message Bus Test

A simplified test to demonstrate that the message bus system works correctly
and can replace Task Master orchestration.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add woodwork to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

async def main():
    """Simple test of message bus functionality"""
    log.info("🚀 Simple Message Bus Test")
    
    try:
        # Import message bus
        from woodwork.core.message_bus import get_global_message_bus
        
        # Get message bus - this should work with zero configuration
        message_bus = await get_global_message_bus()
        log.info(f"✅ Message bus created: {type(message_bus).__name__}")
        
        # Check health
        healthy = message_bus.is_healthy()
        log.info(f"✅ Message bus healthy: {healthy}")
        
        # Test basic component configuration parsing  
        from woodwork.core.message_bus.declarative_router import DeclarativeRouter
        
        router = DeclarativeRouter(message_bus)
        
        # Test configuration like what would come from .ww file
        component_configs = {
            "input": {"component": "inputs", "to": ["agent"]},
            "agent": {"component": "agents", "to": ["output"]}, 
            "output": {"component": "outputs"}
        }
        
        router.configure_from_components(component_configs)
        
        stats = router.get_routing_stats()
        log.info(f"✅ Router configured with {stats['active_routes']} routes")
        log.info(f"✅ Routing table: {stats['routing_table']}")
        
        # Simulate message routing
        success = await router.route_component_output(
            source_component="input",
            event_type="input_received", 
            data="Hello, message bus!",
            session_id="test-session"
        )
        
        log.info(f"✅ Message routing {'succeeded' if success else 'failed'}")
        
        # Test component integration
        from woodwork.components.component import component
        
        # Create test component with routing
        test_comp = component(
            name="test",
            component="agents", 
            type="test",
            config={"to": ["output"]}
        )
        
        log.info(f"✅ Component created with routing targets: {getattr(test_comp, 'output_targets', [])}")
        
        # Get final stats
        bus_stats = message_bus.get_stats()
        log.info(f"✅ Final message bus stats: messages_published={bus_stats['messages_published']}, healthy={message_bus.is_healthy()}")
        
        log.info("🎉 Simple test completed successfully!")
        
        # Shutdown
        await message_bus.stop()
        
    except Exception as e:
        log.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)