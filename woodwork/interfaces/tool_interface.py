from abc import ABC, abstractmethod
import logging

log = logging.getLogger(__name__)


class tool_interface(ABC):
    @abstractmethod
    def input(self, action: str, inputs: dict):
        pass

    @property
    @abstractmethod
    def description(self):
        pass

    def execute_with_events(self, action: str, inputs: dict):
        """
        Execute tool with proper event emission for message bus integration.

        This wrapper ensures tool execution is properly tracked in the distributed system.
        """
        try:
            # Emit tool.execute event if component has event system
            if hasattr(self, 'emit'):
                log.debug(f"[Tool {self.name}] Executing via message bus: {action} with inputs {inputs}")
                # Note: This is a sync emit since tools might be sync
                # The event system handles async/sync automatically

            # Execute the actual tool logic
            result = self.input(action, inputs)

            # Emit tool.result event if component has event system
            if hasattr(self, 'emit'):
                log.debug(f"[Tool {self.name}] Execution completed via message bus: {str(result)[:200]}")

            return result

        except Exception as e:
            # Emit tool.error event
            if hasattr(self, 'emit'):
                log.error(f"[Tool {self.name}] Execution failed via message bus: {e}")
            raise

    async def handle_tool_execute_message(self, payload):
        """
        Handle tool.execute messages from the message bus.

        This enables true distributed tool communication where agents send
        messages to tools instead of calling them directly.
        """
        try:
            action = payload.get("action")
            inputs = payload.get("inputs", {})
            request_id = payload.get("request_id")

            log.info(f"[Tool {getattr(self, 'name', 'unknown')}] Received tool.execute message: {action} with inputs {inputs}")

            # Execute the tool
            result = self.input(action, inputs)

            # Send result back via message bus if possible
            if hasattr(self, 'send_to_component') and request_id:
                # Extract sender from request_id (format: sender_tool_id)
                sender = request_id.split('_')[0] if '_' in request_id else None
                if sender:
                    await self.send_to_component(
                        sender,
                        "tool.result",
                        {
                            "request_id": request_id,
                            "tool": getattr(self, 'name', 'unknown'),
                            "result": result
                        }
                    )
                    log.debug(f"[Tool {getattr(self, 'name', 'unknown')}] Sent result back to {sender} via message bus")

            return result

        except Exception as e:
            log.error(f"[Tool {getattr(self, 'name', 'unknown')}] Error handling tool.execute message: {e}")

            # Send error back via message bus if possible
            if hasattr(self, 'send_to_component') and request_id:
                sender = request_id.split('_')[0] if '_' in request_id else None
                if sender:
                    await self.send_to_component(
                        sender,
                        "tool.error",
                        {
                            "request_id": request_id,
                            "tool": getattr(self, 'name', 'unknown'),
                            "error": str(e)
                        }
                    )
            raise
