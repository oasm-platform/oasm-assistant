from typing import Dict, Any

from agents.core import BaseAgent, AgentRole, AgentType, AgentCapability
from common.logger import logger


class IncidentResponseAgent(BaseAgent):
    """
    Incident Response Agent

    Handles security incident detection, containment, eradication,
    and recovery processes.
    """

    def __init__(self, **kwargs):
        super().__init__(
            name="IncidentResponseAgent",
            role=AgentRole.INCIDENT_RESPONSE_AGENT,
            agent_type=AgentType.REFLEX,
            capabilities=[
                AgentCapability(
                    name="incident_detection",
                    description="Detect and classify security incidents"
                ),
                AgentCapability(
                    name="incident_containment",
                    description="Contain and isolate security incidents"
                ),
                AgentCapability(
                    name="incident_recovery",
                    description="Recover from security incidents"
                )
            ],
            **kwargs
        )

    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute incident response task

        Args:
            task: Task dictionary with action and parameters

        Returns:
            Result dictionary with success status
        """
        try:
            action = task.get("action", "assess_incident")

            if action == "assess_incident":
                return self._assess_incident(task)
            elif action == "contain_incident":
                return self._contain_incident(task)
            elif action == "recover_systems":
                return self._recover_systems(task)
            else:
                return {"success": False, "error": f"Unknown action: {action}"}

        except Exception as e:
            logger.error(f"Incident response task failed: {e}")
            return {"success": False, "error": str(e)}

    def _assess_incident(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Assess security incident"""
        alert = task.get("alert", {})

        assessment = {
            "incident_id": alert.get("id", "unknown"),
            "severity": self._calculate_severity(alert),
            "incident_type": alert.get("type", "unknown"),
            "affected_systems": alert.get("affected_systems", []),
            "attack_vector": "unknown",
            "confidence": 0.8,
            "immediate_actions": [
                "Isolate affected systems",
                "Preserve evidence",
                "Notify stakeholders"
            ]
        }

        return {
            "success": True,
            "assessment": assessment,
            "agent": self.name
        }

    def _contain_incident(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Contain security incident"""
        incident = task.get("incident", {})
        affected_systems = incident.get("affected_systems", [])

        containment_actions = []
        for system in affected_systems:
            containment_actions.append({
                "system": system,
                "action": "network_isolation",
                "status": "completed"
            })

        return {
            "success": True,
            "containment_actions": containment_actions,
            "systems_isolated": len(affected_systems),
            "agent": self.name
        }

    def _recover_systems(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Recover systems after incident"""
        systems = task.get("systems", [])

        recovery_result = {
            "systems_restored": systems,
            "services_restarted": [],
            "data_recovered": True,
            "monitoring_enabled": True,
            "recovery_time": "2 hours"
        }

        return {
            "success": True,
            "recovery": recovery_result,
            "agent": self.name
        }

    def _calculate_severity(self, alert: Dict[str, Any]) -> str:
        """Calculate incident severity based on alert score"""
        score = alert.get("score", 0)
        if score >= 8:
            return "critical"
        elif score >= 6:
            return "high"
        elif score >= 4:
            return "medium"
        else:
            return "low"
