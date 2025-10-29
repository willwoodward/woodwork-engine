"""
Conversation Session - Maintains context across multiple user inputs
"""
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class ConversationSession:
    """Lightweight session to maintain agent context across inputs"""
    id: str
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    workflow_variables: Dict[str, Any] = field(default_factory=dict)
    current_prompt: str = ""
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)

    def add_turn(self, role: str, content: str):
        """Add conversation turn (user or assistant message)"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })
        self.last_activity = time.time()
