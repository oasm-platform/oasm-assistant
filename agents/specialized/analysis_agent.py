from typing import Dict, Any, List

from agents.core import BaseAgent, AgentRole, AgentType, AgentCapability
from common.logger import logger
from llms.prompts import SecurityAgentPrompts


class AnalysisAgent(BaseAgent):
    def __init__(self, **kwargs):
        super().__init__(
            name="AnalysisAgent",
            role=AgentRole.ANALYSIS_AGENT,
            agent_type=AgentType.GOAL_BASED,
            capabilities=[
                AgentCapability(
                    name="security_analysis",
                    description="Perform comprehensive security analysis",
                    tools=["static_analysis", "dynamic_analysis", "behavioral_analysis"]
                ),
                AgentCapability(
                    name="forensic_analysis",
                    description="Conduct digital forensics and incident analysis",
                    tools=["memory_analysis", "disk_forensics", "network_forensics"]
                ),
                AgentCapability(
                    name="malware_analysis",
                    description="Analyze malicious software and artifacts",
                    tools=["sandbox_analysis", "reverse_engineering", "signature_detection"]
                )
            ],
            **kwargs
        )

    def setup_tools(self) -> List[Any]:
        return [
            "volatility",
            "wireshark",
            "ida_pro",
            "ghidra",
            "cuckoo_sandbox",
            "yara_rules",
            "strings_analyzer",
            "entropy_calculator"
        ]

    def create_prompt_template(self) -> str:
        return SecurityAgentPrompts.get_analysis_prompt()

    def process_observation(self, observation: Any) -> Dict[str, Any]:
        return {
            "analysis_type": "unknown",
            "findings": [],
            "severity": "low",
            "confidence": 0.0,
            "artifacts": [],
            "recommendations": []
        }

    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        try:
            action = task.get("action", "analyze_artifact")

            if action == "analyze_artifact":
                return self._analyze_artifact(task)
            elif action == "memory_analysis":
                return self._memory_analysis(task)
            elif action == "network_analysis":
                return self._network_analysis(task)
            elif action == "malware_analysis":
                return self._malware_analysis(task)
            elif action == "behavioral_analysis":
                return self._behavioral_analysis(task)
            else:
                return {"success": False, "error": f"Unknown action: {action}"}

        except Exception as e:
            logger.error(f"Analysis task failed: {e}")
            return {"success": False, "error": str(e)}

    def _analyze_artifact(self, task: Dict[str, Any]) -> Dict[str, Any]:
        artifact = task.get("artifact", {})
        artifact_type = artifact.get("type", "unknown")

        analysis_result = {
            "artifact_id": artifact.get("id", "unknown"),
            "artifact_type": artifact_type,
            "file_hash": artifact.get("hash", ""),
            "size": artifact.get("size", 0),
            "analysis_techniques": ["static", "dynamic"],
            "findings": [],
            "malicious": False,
            "confidence": 0.7
        }

        return {
            "success": True,
            "analysis": analysis_result,
            "agent": self.name
        }

    def _memory_analysis(self, task: Dict[str, Any]) -> Dict[str, Any]:
        memory_dump = task.get("memory_dump", {})

        analysis_result = {
            "processes": [],
            "network_connections": [],
            "injected_code": [],
            "suspicious_activities": [],
            "extracted_artifacts": [],
            "analysis_profile": memory_dump.get("profile", "unknown")
        }

        return {
            "success": True,
            "memory_analysis": analysis_result,
            "agent": self.name
        }

    def _network_analysis(self, task: Dict[str, Any]) -> Dict[str, Any]:
        pcap_file = task.get("pcap_file", {})

        analysis_result = {
            "protocols": [],
            "suspicious_flows": [],
            "extracted_files": [],
            "indicators": [],
            "communication_patterns": [],
            "total_packets": 0
        }

        return {
            "success": True,
            "network_analysis": analysis_result,
            "agent": self.name
        }

    def _malware_analysis(self, task: Dict[str, Any]) -> Dict[str, Any]:
        sample = task.get("sample", {})

        analysis_result = {
            "family": "unknown",
            "behaviors": [],
            "capabilities": [],
            "network_indicators": [],
            "file_indicators": [],
            "registry_changes": [],
            "sandbox_results": {},
            "static_analysis": {},
            "classification": "unknown"
        }

        return {
            "success": True,
            "malware_analysis": analysis_result,
            "agent": self.name
        }

    def _behavioral_analysis(self, task: Dict[str, Any]) -> Dict[str, Any]:
        target = task.get("target", {})

        analysis_result = {
            "behaviors_observed": [],
            "anomalies_detected": [],
            "baseline_deviation": 0.0,
            "risk_score": 0.0,
            "timeline": [],
            "patterns": []
        }

        return {
            "success": True,
            "behavioral_analysis": analysis_result,
            "agent": self.name
        }