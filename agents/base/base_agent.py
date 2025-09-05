"""
Simplified base agent class for OASM Assistant - Q&A only version
"""
from typing import Dict, Any, Callable
from abc import ABC, abstractmethod
import asyncio

from .agent_state import AgentState, AgentStatus
from messaging.agent_messaging import AgentMessageHandler
from common.exceptions.agent_error_handler import AgentErrorHandler


class BaseAgent(ABC):
    """Simplified base agent class for OASM Assistant with Q&A functionality only"""
    
    def __init__(self, agent_id: str, name: str = "BaseAgent"):
        self.agent_id = agent_id
        self.name = name
        
        self.state = AgentState(agent_id=agent_id)
        
        self.message_handler = AgentMessageHandler(agent_id, name)
        self.error_handler = AgentErrorHandler(name)
    
    def update_status(self, status: AgentStatus) -> None:
        """Update agent status"""
        self.state.update_status(status)
    
    def register_message_handler(self, message_type: str, handler: Callable) -> None:
        """Register a message handler for a specific message type"""
        self.message_handler.register_message_handler(message_type, handler)
    
    def send_message(self, recipient_id: str, message_type: str, content: Dict[str, Any]) -> None:
        """Send a message to another agent or system component"""
        self.message_handler.send_message(recipient_id, message_type, content)
    
    async def process_messages(self) -> None:
        """Process all messages in the queue"""
        await self.message_handler.process_messages(
            error_handler=lambda e, ctx: self.error_handler.handle_error(
                e, ctx, None, self.state, self.update_status)
        )
    
    @abstractmethod
    async def respond(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Abstract method for generating responses - must be implemented by subclasses"""
        pass
    
    def add_recovery_strategy(self, strategy: Callable) -> None:
        """Add a recovery strategy for error handling"""
        self.error_handler.add_recovery_strategy(strategy)
    
    def reset_error_count(self) -> None:
        """Reset the error count"""
        self.error_handler.reset_error_count()

    
    async def run(self) -> None:
        """Main run loop for the agent"""
        print(f"[{self.name}] Agent started")
        self.update_status(AgentStatus.IDLE)
        
        try:
            # Main agent loop
            while self.state.status != AgentStatus.FINISHED:
                # Process messages
                await self.process_messages()
                
                # Small delay to prevent busy waiting
                await asyncio.sleep(0.1)
                
        except Exception as e:
            await self.error_handler.handle_error(
                e, {"context": "main_loop"}, 
                None, self.state, self.update_status)
        finally:
            print(f"[{self.name}] Agent stopped")