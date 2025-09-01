"""
Agent state management for OASM Assistant
"""
from typing import Dict, Any, List, Optional
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


class AgentGoal(BaseModel):
    """Represents a goal for the agent"""
    id: str
    description: str
    status: str = "pending"  # pending, in_progress, completed, failed
    priority: int = 1
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


class AgentContext(BaseModel):
    """Represents the context for the agent"""
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)
    current_task: Optional[str] = None
    environment_state: Dict[str, Any] = Field(default_factory=dict)
    user_preferences: Dict[str, Any] = Field(default_factory=dict)


class AgentState(BaseModel):
    """Main agent state class"""
    agent_id: str
    status: AgentStatus = AgentStatus.IDLE
    goals: List[AgentGoal] = Field(default_factory=list)
    context: AgentContext = Field(default_factory=AgentContext)
    memory: Dict[str, Any] = Field(default_factory=dict)
    tools: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)
    
    def update_status(self, status: AgentStatus) -> None:
        """Update agent status"""
        self.status = status
        self.last_updated = datetime.now()
    
    def add_goal(self, goal: AgentGoal) -> None:
        """Add a new goal to the agent"""
        self.goals.append(goal)
        self.last_updated = datetime.now()
    
    def update_goal_status(self, goal_id: str, status: str) -> bool:
        """Update the status of a specific goal"""
        for goal in self.goals:
            if goal.id == goal_id:
                goal.status = status
                if status in ["completed", "failed"]:
                    goal.completed_at = datetime.now()
                self.last_updated = datetime.now()
                return True
        return False
    
    def add_to_context_history(self, message: Dict[str, Any]) -> None:
        """Add a message to conversation history"""
        self.context.conversation_history.append(message)
        self.last_updated = datetime.now()
    
    def update_context(self, key: str, value: Any) -> None:
        """Update context information"""
        setattr(self.context, key, value)
        self.last_updated = datetime.now()
    
    def set_environment_state(self, state: Dict[str, Any]) -> None:
        """Update the environment state in context"""
        self.context.environment_state = state
        self.last_updated = datetime.now()