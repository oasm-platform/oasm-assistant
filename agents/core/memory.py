from typing import Dict, Any, List
from datetime import datetime
from collections import deque
from common.logger import logger


class AgentMemory:
    """Simplified memory system for OASM agents"""

    def __init__(self, agent_id: str, max_working_memory: int = 100):
        self.agent_id = agent_id
        self.max_working_memory = max_working_memory

        # Simple working memory for recent observations
        self.working_memory = deque(maxlen=max_working_memory)
        self.observations: List[Dict[str, Any]] = []

        logger.info(f"Memory initialized for agent {agent_id}")

    def add_observation(self, observation: Dict[str, Any]):
        """Add observation to memory"""
        observation_entry = {
            **observation,
            "timestamp": datetime.now(datetime.timezone.utc),
            "agent_id": self.agent_id
        }

        self.working_memory.append(observation_entry)
        self.observations.append(observation_entry)

        # Keep only last 1000 observations
        if len(self.observations) > 1000:
            self.observations = self.observations[-1000:]

    def get_recent_observations(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get recent observations"""
        return list(self.working_memory)[-count:]

    def get_all_observations(self) -> List[Dict[str, Any]]:
        """Get all stored observations"""
        return self.observations.copy()

    def clear_memory(self):
        """Clear all memory"""
        self.working_memory.clear()
        self.observations.clear()
        logger.info(f"Memory cleared for agent {self.agent_id}")