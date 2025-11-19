from typing import Dict, Any, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from agents.core import BaseAgent, AgentRole, AgentType, AgentCapability
from common.logger import logger
from agents.specialized.analysis_agent import AnalysisAgent


class OrchestrationAgent(BaseAgent):
    """
    Orchestration Agent for coordinating multi-agent workflows

    This agent manages workflow coordination, resource allocation,
    and communication between specialized agents.
    """

    def __init__(
        self,
        db_session: Optional[Session] = None,
        workspace_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        **kwargs
    ):
        """
        Initialize Orchestration Agent

        Args:
            db_session: Database session for agents
            workspace_id: Workspace ID for MCP integration (optional)
            user_id: User ID for MCP integration (optional)
        """
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

        # Store MCP context
        self.db_session = db_session
        self.workspace_id = workspace_id
        self.user_id = user_id

        # Initialize specialized agents with MCP context
        self.analysis_agent = None
        if db_session and workspace_id and user_id:
            self.analysis_agent = AnalysisAgent(
                db_session=db_session,
                workspace_id=workspace_id,
                user_id=user_id
            )
            logger.debug(f"OrchestrationAgent initialized with MCP context")
        elif db_session:
            self.analysis_agent = AnalysisAgent(db_session=db_session)
            logger.debug("OrchestrationAgent initialized without MCP context")

    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute orchestration task

        Args:
            task: Task dictionary with action and parameters

        Returns:
            Result dictionary with success status
        """
        try:
            action = task.get("action", "coordinate_workflow")

            if action == "coordinate_workflow":
                return self._coordinate_workflow(task)
            elif action == "analyze_vulnerabilities":
                return self._analyze_vulnerabilities(task)
            else:
                return {"success": False, "error": f"Unknown action: {action}"}

        except Exception as e:
            logger.error(f"Orchestration task failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _coordinate_workflow(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Coordinate security workflow"""
        workflow = task.get("workflow", {})
        workflow_type = workflow.get("type", "security_analysis")

        coordination_result = {
            "workflow_id": workflow.get("id", "workflow_001"),
            "workflow_type": workflow_type,
            "agents_assigned": ["AnalysisAgent"],
            "status": "initiated"
        }

        return {
            "success": True,
            "coordination": coordination_result,
            "agent": self.name
        }

    def _analyze_vulnerabilities(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delegate vulnerability analysis to Analysis Agent

        Args:
            task: Task containing scan_results or question

        Returns:
            Analysis result from AnalysisAgent
        """
        if not self.analysis_agent:
            return {
                "success": False,
                "error": "Analysis Agent not initialized. Database session required.",
                "agent": self.name
            }

        try:
            scan_results = task.get("scan_results")
            question = task.get("question", "Analyze security vulnerabilities")

            if scan_results:
                logger.info(f"Delegating to AnalysisAgent: {len(scan_results)} scan results")
            else:
                logger.info(f"Delegating to AnalysisAgent with question")

            # Delegate to analysis agent
            result = self.analysis_agent.execute_task({
                "action": "analyze_vulnerabilities",
                "question": question,
                "scan_results": scan_results
            })

            # Add orchestration metadata
            result["orchestrated_by"] = self.name
            result["workflow_id"] = task.get("workflow_id", "auto-generated")

            return result

        except Exception as e:
            logger.error(f"Analysis delegation failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Analysis failed: {str(e)}",
                "agent": self.name
            }
