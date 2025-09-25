from typing import Dict, Any, List

from agents.core import BaseAgent, AgentRole, AgentType, AgentCapability
from common.logger import logger
from llms.prompts import SecurityAgentPrompts


class ThreatDetectionAgent(BaseAgent):
    def __init__(self, **kwargs):
        super().__init__(
            name="ThreatDetectionAgent",
            role=AgentRole.THREAT_ANALYST,
            agent_type=AgentType.GOAL_BASED,
            capabilities=[
                AgentCapability(
                    name="threat_analysis",
                    description="Analyze and identify security threats",
                    tools=["threat_intelligence", "anomaly_detection"]
                )
            ],
            **kwargs
        )

    def setup_tools(self) -> List[Any]:
        return ["threat_intelligence", "yara_scanner", "ioc_analyzer"]

    def create_prompt_template(self) -> str:
        return SecurityAgentPrompts.get_threat_detection_prompt()

    def process_observation(self, observation: Any) -> Dict[str, Any]:
        return {
            "threats_detected": 0,
            "risk_level": "low",
            "indicators": [],
            "recommendations": []
        }

    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        try:
            action = task.get("action", "analyze_threat")

            if action == "analyze_threat":
                return self._analyze_threat(task)
            elif action == "scan_indicators":
                return self._scan_indicators(task)
            else:
                return {"success": False, "error": f"Unknown action: {action}"}

        except Exception as e:
            logger.error(f"Threat detection task failed: {e}")
            return {"success": False, "error": str(e)}

    def _analyze_threat(self, task: Dict[str, Any]) -> Dict[str, Any]:
        target = task.get("target", "unknown")

        analysis_result = {
            "target": target,
            "threats_found": [],
            "risk_assessment": "medium",
            "confidence": 0.7,
            "recommendations": [
                "Monitor for suspicious activities",
                "Update security policies",
                "Enhance monitoring capabilities"
            ]
        }

        return {
            "success": True,
            "analysis": analysis_result,
            "agent": self.name
        }

    def _scan_indicators(self, task: Dict[str, Any]) -> Dict[str, Any]:
        indicators = task.get("indicators", [])

        return {
            "success": True,
            "indicators_processed": len(indicators),
            "matches_found": 0,
            "scan_results": [],
            "agent": self.name
        }