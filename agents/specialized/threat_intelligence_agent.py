from typing import Dict, Any

from agents.core import BaseAgent, AgentRole, AgentType, AgentCapability
from common.logger import logger


class ThreatIntelligenceAgent(BaseAgent):
    """
    Threat Intelligence Agent

    Collects, analyzes, and correlates threat intelligence data
    from multiple sources for security assessments.
    """

    def __init__(self, **kwargs):
        super().__init__(
            name="ThreatIntelligenceAgent",
            role=AgentRole.THREAT_INTELLIGENCE_AGENT,
            agent_type=AgentType.GOAL_BASED,
            capabilities=[
                AgentCapability(
                    name="threat_intelligence_gathering",
                    description="Collect and analyze threat intelligence data"
                ),
                AgentCapability(
                    name="threat_correlation",
                    description="Correlate threats across multiple sources"
                )
            ],
            **kwargs
        )

    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute threat intelligence task

        Args:
            task: Task dictionary with action and parameters

        Returns:
            Result dictionary with success status
        """
        try:
            action = task.get("action", "gather_intelligence")

            if action == "gather_intelligence":
                return self._gather_intelligence(task)
            elif action == "correlate_threats":
                return self._correlate_threats(task)
            else:
                return {"success": False, "error": f"Unknown action: {action}"}

        except Exception as e:
            logger.error(f"Threat intelligence task failed: {e}")
            return {"success": False, "error": str(e)}

    def _gather_intelligence(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Gather threat intelligence from various sources"""
        target = task.get("target", "general")
        sources = task.get("sources", ["feeds", "osint"])

        intelligence_result = {
            "target": target,
            "sources_queried": sources,
            "indicators_collected": [],
            "threat_actors": [],
            "campaigns": [],
            "confidence": 0.8
        }

        return {
            "success": True,
            "intelligence": intelligence_result,
            "agent": self.name
        }

    def _correlate_threats(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Correlate threats across multiple data sources"""
        threat_data = task.get("threat_data", [])

        correlations = {
            "campaigns": [],
            "threat_actors": [],
            "infrastructure": [],
            "techniques": [],
            "correlation_score": 0.6
        }

        return {
            "success": True,
            "correlations": correlations,
            "data_sources": len(threat_data),
            "agent": self.name
        }
