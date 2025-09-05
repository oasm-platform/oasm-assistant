"""
Agent state management for OASM Assistant
"""
from typing import Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class AgentStatus(str, Enum):
    """Agent status enumeration"""
    IDLE = "idle"
    THINKING = "thinking"
    ACTING = "acting"
    WAITING = "waiting"
    ERROR = "error"
    FINISHED = "finished"


class AgentContext(BaseModel):
    """Represents the context for the agent"""
    user_preferences: Dict[str, Any] = Field(default_factory=dict)


class AgentState(BaseModel):
    """Main agent state class"""
    agent_id: str
    status: AgentStatus = AgentStatus.IDLE
    context: AgentContext = Field(default_factory=AgentContext)
    created_at: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)
    
    def update_status(self, status: AgentStatus) -> None:
        """Update agent status"""
        self.status = status
        self.last_updated = datetime.now()
    
    def update_context(self, key: str, value: Any) -> None:
        """Update context information"""
        setattr(self.context, key, value)
        self.last_updated = datetime.now()