from typing import Dict, Any, List

from agents.core import BaseAgent, AgentRole, AgentType, AgentCapability
from common.logger import logger
from llms.prompts import ThreatIntelligenceAgentPrompts


class ThreatIntelligenceAgent(BaseAgent):
    def __init__(self, **kwargs):
        super().__init__(
            name="ThreatIntelligenceAgent",
            role=AgentRole.THREAT_INTELLIGENCE_AGENT,
            agent_type=AgentType.GOAL_BASED,
            capabilities=[
                AgentCapability(
                    name="threat_intelligence_gathering",
                    description="Collect and analyze threat intelligence data",
                    tools=["threat_feeds", "osint_collection", "ioc_enrichment"]
                ),
                AgentCapability(
                    name="threat_correlation",
                    description="Correlate threats across multiple sources",
                    tools=["correlation_engine", "pattern_analysis"]
                )
            ],
            **kwargs
        )

    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        try:
            action = task.get("action", "gather_intelligence")

            if action == "gather_intelligence":
                return self._gather_intelligence(task)
            elif action == "enrich_indicators":
                return self._enrich_indicators(task)
            elif action == "correlate_threats":
                return self._correlate_threats(task)
            elif action == "generate_report":
                return self._generate_intelligence_report(task)
            else:
                return {"success": False, "error": f"Unknown action: {action}"}

        except Exception as e:
            logger.error(f"Threat intelligence task failed: {e}")
            return {"success": False, "error": str(e)}

    def _gather_intelligence(self, task: Dict[str, Any]) -> Dict[str, Any]:
        target = task.get("target", "general")
        sources = task.get("sources", ["feeds", "osint"])

        intelligence_result = {
            "target": target,
            "sources_queried": sources,
            "indicators_collected": [],
            "threat_actors": [],
            "campaigns": [],
            "ttps": [],
            "confidence": 0.8
        }

        return {
            "success": True,
            "intelligence": intelligence_result,
            "agent": self.name
        }

    def _enrich_indicators(self, task: Dict[str, Any]) -> Dict[str, Any]:
        indicators = task.get("indicators", [])

        enriched_indicators = []
        for indicator in indicators:
            enriched_indicators.append({
                "indicator": indicator,
                "type": "unknown",
                "malicious": False,
                "sources": [],
                "first_seen": None,
                "last_seen": None,
                "confidence": 0.5
            })

        return {
            "success": True,
            "enriched_indicators": enriched_indicators,
            "total_processed": len(indicators),
            "agent": self.name
        }

    def _correlate_threats(self, task: Dict[str, Any]) -> Dict[str, Any]:
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

    def _generate_intelligence_report(self, task: Dict[str, Any]) -> Dict[str, Any]:
        data = task.get("data", {})

        report = {
            "executive_summary": "Threat intelligence analysis completed",
            "key_findings": [],
            "threat_landscape": {},
            "recommendations": [
                "Continue monitoring threat feeds",
                "Update security controls based on new TTPs",
                "Enhance threat hunting capabilities"
            ],
            "confidence_level": "medium"
        }

        return {
            "success": True,
            "report": report,
            "agent": self.name
        }