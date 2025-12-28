from typing import Dict, Any, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from agents.core import BaseAgent, AgentRole, AgentType, AgentCapability
from common.logger import logger
from agents.specialized.analysis_agent import AnalysisAgent


class OrchestrationAgent(BaseAgent):
    """Coordinates multi-agent workflows and delegates tasks"""

    def __init__(
        self,
        db_session: Optional[Session] = None,
        workspace_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        **kwargs
    ):
        super().__init__(
            name="OrchestrationAgent",
            role=AgentRole.ORCHESTRATION_AGENT,
            agent_type=AgentType.GOAL_BASED,
            capabilities=[
                AgentCapability(
                    name="workflow_coordination",
                    description="Coordinate security workflows and agent interactions"
                ),
                AgentCapability(
                    name="decision_making",
                    description="Make strategic security decisions"
                )
            ],
            **kwargs
        )

        self.db_session = db_session
        self.workspace_id = workspace_id
        self.user_id = user_id
        self.analysis_agent = None
        
        llm_config = kwargs.get('llm_config', {})
        
        if db_session:
            self.analysis_agent = AnalysisAgent(
                db_session=db_session,
                workspace_id=workspace_id,
                user_id=user_id,
                llm_config=llm_config
            )
            logger.debug(f"OrchestrationAgent initialized with {'full' if workspace_id and user_id else 'partial'} MCP context")

    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task by action type"""
        try:
            action = task.get("action", "coordinate_workflow")
            
            if action == "coordinate_workflow":
                workflow = task.get("workflow", {})
                return {
                    "success": True,
                    "coordination": {
                        "workflow_id": workflow.get("id", "workflow_001"),
                        "workflow_type": workflow.get("type", "security_analysis"),
                        "agents_assigned": ["AnalysisAgent"],
                        "status": "initiated"
                    },
                    "agent": self.name
                }
            
            if action == "analyze_vulnerabilities":
                if not self.analysis_agent:
                    return {
                        "success": False,
                        "error": "Analysis Agent not initialized. Database session required.",
                        "agent": self.name
                    }
                
                # Delegate directly to analysis agent
                result = self.analysis_agent.execute_task({
                    "action": "analyze_vulnerabilities",
                    "question": task.get("question", "Analyze security vulnerabilities"),
                    "scan_results": task.get("scan_results")
                })
                
                # Add orchestration metadata
                result.update({
                    "orchestrated_by": self.name,
                    "workflow_id": task.get("workflow_id", "auto-generated")
                })
                return result
            
            return {"success": False, "error": f"Unknown action: {action}"}

        except Exception as e:
            logger.error("Orchestration task failed: {}", e)
            return {"success": False, "error": str(e)}
