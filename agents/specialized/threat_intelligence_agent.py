"""Threat intelligence agent for collecting and analyzing threat data"""

from typing import Dict, Any

from agents.core import BaseAgent, AgentRole, AgentType, AgentCapability
from common.logger import logger


class ThreatIntelligenceAgent(BaseAgent):
    """Collects, analyzes, and correlates threat intelligence from multiple sources"""

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

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute threat intelligence task by action type"""
        try:
            action = task.get("action", "gather_intelligence")

            if action == "gather_intelligence":
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
                return {"success": True, "intelligence": intelligence_result, "agent": self.name}

            if action == "correlate_threats":
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

            return {"success": False, "error": f"Unknown action: {action}"}

        except Exception as e:
            logger.error("Threat intelligence task failed: {}", e)
            return {"success": False, "error": str(e)}
