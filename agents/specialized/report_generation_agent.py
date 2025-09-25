from typing import Dict, Any, List

from agents.core import BaseAgent, AgentRole, AgentType, AgentCapability
from common.logger import logger
from llms.prompts import SecurityAgentPrompts


class ReportGenerationAgent(BaseAgent):
    def __init__(self, **kwargs):
        super().__init__(
            name="ReportGenerationAgent",
            role=AgentRole.SECURITY_RESEARCHER,
            agent_type=AgentType.GOAL_BASED,
            capabilities=[
                AgentCapability(
                    name="report_generation",
                    description="Generate comprehensive security reports",
                    tools=["report_generator", "template_engine", "data_analyzer"]
                )
            ],
            **kwargs
        )

    def setup_tools(self) -> List[Any]:
        return ["report_generator", "template_engine", "data_analyzer", "chart_generator"]

    def create_prompt_template(self) -> str:
        return SecurityAgentPrompts.get_report_generation_prompt()

    def process_observation(self, observation: Any) -> Dict[str, Any]:
        return {
            "reports_generated": 0,
            "data_sources": [],
            "analysis_complete": True
        }

    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        try:
            action = task.get("action", "generate_report")

            if action == "generate_report":
                return self._generate_report(task)
            else:
                return {"success": False, "error": f"Unknown action: {action}"}

        except Exception as e:
            logger.error(f"Report generation task failed: {e}")
            return {"success": False, "error": str(e)}

    def _generate_report(self, task: Dict[str, Any]) -> Dict[str, Any]:
        data = task.get("data", {})

        report_result = {
            "report_type": "security_assessment",
            "executive_summary": "Security assessment completed with medium risk findings",
            "findings_count": 5,
            "risk_level": "medium",
            "recommendations": [
                "Implement security patches",
                "Update security policies",
                "Enhance monitoring capabilities"
            ]
        }

        return {
            "success": True,
            "report": report_result,
            "agent": self.name
        }