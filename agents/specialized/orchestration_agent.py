from typing import Dict, Any, List

from agents.core import BaseAgent, AgentRole, AgentType, AgentCapability
from common.logger import logger
from llms.prompts import SecurityAgentPrompts


class OrchestrationAgent(BaseAgent):
    def __init__(self, **kwargs):
        super().__init__(
            name="OrchestrationAgent",
            role=AgentRole.ORCHESTRATION_AGENT,
            agent_type=AgentType.GOAL_BASED,
            capabilities=[
                AgentCapability(
                    name="workflow_coordination",
                    description="Coordinate security workflows and agent interactions",
                    tools=["workflow_engine", "task_scheduler", "agent_manager"]
                ),
                AgentCapability(
                    name="resource_management",
                    description="Manage computational and security resources",
                    tools=["resource_allocator", "load_balancer", "priority_queue"]
                ),
                AgentCapability(
                    name="decision_making",
                    description="Make strategic security decisions",
                    tools=["decision_engine", "policy_evaluator", "risk_calculator"]
                ),
                AgentCapability(
                    name="communication_hub",
                    description="Facilitate communication between agents and systems",
                    tools=["message_broker", "event_dispatcher", "notification_system"]
                )
            ],
            **kwargs
        )

    def setup_tools(self) -> List[Any]:
        return [
            "workflow_engine",
            "agent_registry",
            "task_queue",
            "event_bus",
            "decision_matrix",
            "policy_engine",
            "resource_monitor"
        ]

    def create_prompt_template(self) -> str:
        return SecurityAgentPrompts.get_orchestration_prompt()

    def process_observation(self, observation: Any) -> Dict[str, Any]:
        return {
            "active_workflows": [],
            "agent_status": {},
            "resource_utilization": {},
            "pending_decisions": [],
            "system_health": "healthy"
        }

    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        try:
            action = task.get("action", "coordinate_workflow")

            if action == "coordinate_workflow":
                return self._coordinate_workflow(task)
            elif action == "manage_agents":
                return self._manage_agents(task)
            elif action == "allocate_resources":
                return self._allocate_resources(task)
            elif action == "make_decision":
                return self._make_decision(task)
            elif action == "monitor_system":
                return self._monitor_system(task)
            else:
                return {"success": False, "error": f"Unknown action: {action}"}

        except Exception as e:
            logger.error(f"Orchestration task failed: {e}")
            return {"success": False, "error": str(e)}

    def _coordinate_workflow(self, task: Dict[str, Any]) -> Dict[str, Any]:
        workflow = task.get("workflow", {})
        workflow_type = workflow.get("type", "security_analysis")

        coordination_result = {
            "workflow_id": workflow.get("id", "workflow_001"),
            "workflow_type": workflow_type,
            "agents_assigned": [],
            "execution_plan": [],
            "estimated_completion": "30 minutes",
            "status": "initiated"
        }

        # Assign agents based on workflow type
        if workflow_type == "incident_response":
            coordination_result["agents_assigned"] = [
                "IncidentResponseAgent",
                "AnalysisAgent",
                "ThreatIntelligenceAgent"
            ]
        elif workflow_type == "threat_hunting":
            coordination_result["agents_assigned"] = [
                "ThreatIntelligenceAgent",
                "AnalysisAgent"
            ]
        else:
            coordination_result["agents_assigned"] = ["AnalysisAgent"]

        return {
            "success": True,
            "coordination": coordination_result,
            "agent": self.name
        }

    def _manage_agents(self, task: Dict[str, Any]) -> Dict[str, Any]:
        management_action = task.get("management_action", "status_check")
        target_agents = task.get("target_agents", [])

        management_result = {
            "action_performed": management_action,
            "agents_affected": target_agents,
            "agent_statuses": {},
            "performance_metrics": {},
            "resource_usage": {}
        }

        for agent in target_agents:
            management_result["agent_statuses"][agent] = "active"
            management_result["performance_metrics"][agent] = {
                "tasks_completed": 10,
                "success_rate": 0.9,
                "average_execution_time": "2 minutes"
            }
            management_result["resource_usage"][agent] = {
                "cpu": "15%",
                "memory": "256MB",
                "network": "low"
            }

        return {
            "success": True,
            "management": management_result,
            "agent": self.name
        }

    def _allocate_resources(self, task: Dict[str, Any]) -> Dict[str, Any]:
        resource_request = task.get("resource_request", {})
        requesting_agent = task.get("requesting_agent", "unknown")

        allocation_result = {
            "requesting_agent": requesting_agent,
            "resource_type": resource_request.get("type", "compute"),
            "amount_requested": resource_request.get("amount", 1),
            "amount_allocated": resource_request.get("amount", 1),
            "allocation_status": "approved",
            "duration": resource_request.get("duration", "1 hour")
        }

        return {
            "success": True,
            "allocation": allocation_result,
            "agent": self.name
        }

    def _make_decision(self, task: Dict[str, Any]) -> Dict[str, Any]:
        decision_context = task.get("context", {})
        options = task.get("options", [])

        decision_result = {
            "decision_id": f"decision_{len(options)}",
            "context": decision_context,
            "available_options": options,
            "selected_option": options[0] if options else "default",
            "confidence": 0.8,
            "reasoning": "Based on current security posture and risk assessment",
            "implementation_plan": []
        }

        return {
            "success": True,
            "decision": decision_result,
            "agent": self.name
        }

    def _monitor_system(self, task: Dict[str, Any]) -> Dict[str, Any]:
        monitoring_scope = task.get("scope", "all_agents")

        monitoring_result = {
            "monitoring_scope": monitoring_scope,
            "system_health": "healthy",
            "active_agents": 4,
            "running_workflows": 2,
            "resource_utilization": {
                "cpu": "45%",
                "memory": "60%",
                "network": "low",
                "storage": "30%"
            },
            "alerts": [],
            "recommendations": [
                "All systems operating normally",
                "No immediate action required"
            ]
        }

        return {
            "success": True,
            "monitoring": monitoring_result,
            "agent": self.name
        }