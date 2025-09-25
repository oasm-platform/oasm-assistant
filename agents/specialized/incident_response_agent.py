from typing import Dict, Any, List

from agents.core import BaseAgent, AgentRole, AgentType, AgentCapability
from common.logger import logger
from llms.prompts import SecurityAgentPrompts


class IncidentResponseAgent(BaseAgent):
    def __init__(self, **kwargs):
        super().__init__(
            name="IncidentResponseAgent",
            role=AgentRole.INCIDENT_RESPONSE_AGENT,
            agent_type=AgentType.REFLEX,
            capabilities=[
                AgentCapability(
                    name="incident_detection",
                    description="Detect and classify security incidents",
                    tools=["siem_integration", "alert_correlation", "anomaly_detection"]
                ),
                AgentCapability(
                    name="incident_containment",
                    description="Contain and isolate security incidents",
                    tools=["network_isolation", "system_quarantine", "access_control"]
                ),
                AgentCapability(
                    name="incident_recovery",
                    description="Recover from security incidents",
                    tools=["backup_restore", "system_rebuild", "service_restoration"]
                ),
                AgentCapability(
                    name="incident_documentation",
                    description="Document incident response activities",
                    tools=["report_generation", "timeline_creation", "evidence_collection"]
                )
            ],
            **kwargs
        )

    def setup_tools(self) -> List[Any]:
        return [
            "splunk_connector",
            "elastic_siem",
            "firewall_controller",
            "edr_integration",
            "backup_manager",
            "communication_system",
            "ticketing_system"
        ]

    def create_prompt_template(self) -> str:
        return SecurityAgentPrompts.get_incident_response_prompt()

    def process_observation(self, observation: Any) -> Dict[str, Any]:
        return {
            "incident_detected": False,
            "severity": "low",
            "affected_systems": [],
            "response_actions": [],
            "status": "monitoring"
        }

    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        try:
            action = task.get("action", "assess_incident")

            if action == "assess_incident":
                return self._assess_incident(task)
            elif action == "contain_incident":
                return self._contain_incident(task)
            elif action == "eradicate_threat":
                return self._eradicate_threat(task)
            elif action == "recover_systems":
                return self._recover_systems(task)
            elif action == "lessons_learned":
                return self._lessons_learned(task)
            else:
                return {"success": False, "error": f"Unknown action: {action}"}

        except Exception as e:
            logger.error(f"Incident response task failed: {e}")
            return {"success": False, "error": str(e)}

    def _assess_incident(self, task: Dict[str, Any]) -> Dict[str, Any]:
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
        incident = task.get("incident", {})
        affected_systems = incident.get("affected_systems", [])

        containment_actions = []
        for system in affected_systems:
            containment_actions.append({
                "system": system,
                "action": "network_isolation",
                "status": "completed",
                "timestamp": "2024-01-01T00:00:00Z"
            })

        return {
            "success": True,
            "containment_actions": containment_actions,
            "systems_isolated": len(affected_systems),
            "agent": self.name
        }

    def _eradicate_threat(self, task: Dict[str, Any]) -> Dict[str, Any]:
        threat = task.get("threat", {})

        eradication_result = {
            "threat_removed": True,
            "systems_cleaned": [],
            "patches_applied": [],
            "configurations_updated": [],
            "vulnerabilities_closed": [],
            "verification_status": "pending"
        }

        return {
            "success": True,
            "eradication": eradication_result,
            "agent": self.name
        }

    def _recover_systems(self, task: Dict[str, Any]) -> Dict[str, Any]:
        systems = task.get("systems", [])

        recovery_result = {
            "systems_restored": [],
            "services_restarted": [],
            "data_recovered": True,
            "monitoring_enabled": True,
            "recovery_time": "2 hours",
            "verification_tests": []
        }

        return {
            "success": True,
            "recovery": recovery_result,
            "agent": self.name
        }

    def _lessons_learned(self, task: Dict[str, Any]) -> Dict[str, Any]:
        incident = task.get("incident", {})

        lessons = {
            "incident_summary": "Security incident successfully resolved",
            "timeline": [],
            "root_cause": "unknown",
            "improvements": [
                "Update detection rules",
                "Enhance monitoring capabilities",
                "Improve response procedures"
            ],
            "preventive_measures": [
                "Security awareness training",
                "System hardening",
                "Enhanced monitoring"
            ]
        }

        return {
            "success": True,
            "lessons_learned": lessons,
            "agent": self.name
        }

    def _calculate_severity(self, alert: Dict[str, Any]) -> str:
        score = alert.get("score", 0)
        if score >= 8:
            return "critical"
        elif score >= 6:
            return "high"
        elif score >= 4:
            return "medium"
        else:
            return "low"