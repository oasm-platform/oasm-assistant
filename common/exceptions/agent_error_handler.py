"""
Simplified error handling system for OASM agents - Q&A only version
"""
from typing import Callable, Dict, Any
from datetime import datetime
import traceback
from agents.core.state import AgentStatus


class AgentErrorHandler:
    """Handles errors for agents"""
    
    def __init__(self, agent_name: str = "Agent", max_errors: int = 5):
        self.agent_name = agent_name
        self.error_count = 0
        self.max_errors = max_errors
    
    async def handle_error(self, error: Exception, context: Dict[str, Any], 
                          memory_manager, state_manager, status_updater) -> None:
        """Handle errors"""
        self.error_count += 1
        status_updater(AgentStatus.ERROR)
        
        error_info = {
            "error": str(error),
            "type": type(error).__name__,
            "traceback": traceback.format_exc(),
            "context": context,
            "timestamp": datetime.now()
        }
        
        print(f"[{self.agent_name}] Error occurred: {error_info}")
        
        # Reset to idle state
        status_updater(AgentStatus.IDLE)
    
    def reset_error_count(self) -> None:
        """Reset the error count"""
        self.error_count = 0