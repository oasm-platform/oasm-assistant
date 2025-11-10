from typing import Dict, Any
from common.logger import logger
from datetime import datetime



class PerceptionSystem:
    """Simplified perception system for OASM agents"""

    def __init__(self, agent):
        self.agent = agent
        self.last_perception: Dict[str, Any] = {}

        logger.info(f"Perception system initialized for agent {self.agent.name}")

    def perceive(self) -> Dict[str, Any]:
        """Perceive environment and security context"""
        perception_data = {
            "timestamp": datetime.now(),
            "agent_id": self.agent.id,
            "environment_state": self.agent.environment.get_environment_state(),
            "agent_state": {
                "role": self.agent.role.value,
                "capabilities_count": len(self.agent.capabilities)
            }
        }

        self.last_perception = perception_data
        return perception_data

    def get_last_perception(self) -> Dict[str, Any]:
        """Get last perception data"""
        return self.last_perception.copy()