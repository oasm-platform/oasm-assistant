from typing import Dict, Any, List

from agents.core import BaseAgent, AgentRole, AgentType, AgentCapability
from common.logger import logger
from llms.prompts import SecurityAgentPrompts


class WebSecurityAgent(BaseAgent):
    def __init__(self, **kwargs):
        super().__init__(
            name="WebSecurityAgent",
            role=AgentRole.SECURITY_RESEARCHER,
            agent_type=AgentType.GOAL_BASED,
            capabilities=[
                AgentCapability(
                    name="web_security_analysis",
                    description="Perform web application security analysis",
                    tools=["burp_suite", "zap", "nikto", "sqlmap"]
                )
            ],
            **kwargs
        )

    def setup_tools(self) -> List[Any]:
        return ["burp_suite", "zap", "nikto", "sqlmap", "wfuzz"]

    def create_prompt_template(self) -> str:
        return SecurityAgentPrompts.get_web_security_prompt()

    def process_observation(self, observation: Any) -> Dict[str, Any]:
        return {
            "web_vulnerabilities": [],
            "risk_score": 0.0,
            "security_headers": [],
            "ssl_analysis": {}
        }

    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        try:
            action = task.get("action", "analyze_web_security")

            if action == "analyze_web_security":
                return self._analyze_web_security(task)
            else:
                return {"success": False, "error": f"Unknown action: {action}"}

        except Exception as e:
            logger.error(f"Web security task failed: {e}")
            return {"success": False, "error": str(e)}

    def _analyze_web_security(self, task: Dict[str, Any]) -> Dict[str, Any]:
        target = task.get("target", "unknown")

        analysis_result = {
            "target": target,
            "vulnerabilities": [
                {"type": "Missing Security Headers", "severity": "medium"},
                {"type": "SSL Configuration", "severity": "low"}
            ],
            "security_score": 7.5,
            "recommendations": [
                "Implement Content Security Policy",
                "Configure secure headers",
                "Update SSL/TLS configuration"
            ]
        }

        return {
            "success": True,
            "web_analysis": analysis_result,
            "agent": self.name
        }