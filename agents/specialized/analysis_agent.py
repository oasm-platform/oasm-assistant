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
            elif action == "generate_nuclei_template":
                return self._generate_nuclei_template(task)
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

    def _generate_nuclei_template(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a nuclei template based on the provided vulnerability details"""
        question = task.get("question", "")
        vulnerability_data = task.get("vulnerability_data", {})
        target = task.get("target", "")

        # Extract vulnerability type from question
        vuln_type = self._extract_vulnerability_type(question)

        # Generate template based on vulnerability type
        template = self._create_nuclei_yaml_template(vuln_type, question, vulnerability_data, target)

        return {
            "success": True,
            "template_type": "nuclei",
            "vulnerability_type": vuln_type,
            "template": template,
            "agent": self.name
        }

    def _extract_vulnerability_type(self, question: str) -> str:
        """Extract vulnerability type from question"""
        question_lower = question.lower()

        if "xss" in question_lower or "cross-site scripting" in question_lower:
            return "xss"
        elif "sql injection" in question_lower or "sqli" in question_lower:
            return "sqli"
        elif "lfi" in question_lower or "local file inclusion" in question_lower:
            return "lfi"
        elif "rfi" in question_lower or "remote file inclusion" in question_lower:
            return "rfi"
        elif "ssrf" in question_lower or "server-side request forgery" in question_lower:
            return "ssrf"
        elif "csrf" in question_lower or "cross-site request forgery" in question_lower:
            return "csrf"
        elif "rce" in question_lower or "remote code execution" in question_lower:
            return "rce"
        elif "directory traversal" in question_lower or "path traversal" in question_lower:
            return "directory_traversal"
        else:
            return "generic"

    def _create_nuclei_yaml_template(self, vuln_type: str, question: str, vulnerability_data: Dict, target: str) -> Dict[str, Any]:
        """Create a nuclei YAML template structure"""

        template_id = f"{vuln_type}-detection-{hash(question) % 10000:04d}"

        # Base template structure
        template = {
            "id": template_id,
            "name": f"{vuln_type.upper()} Detection Template",
            "description": f"Detects {vuln_type.upper()} vulnerabilities",
            "severity": self._get_severity_for_vuln_type(vuln_type),
            "tags": [vuln_type, "vulnerability", "security"],
            "author": "OASM Assistant",
            "confidence": 0.85,
            "created_at": "2025-09-30",
            "yaml_content": self._generate_yaml_content(vuln_type, template_id)
        }

        # Add specific details based on vulnerability type
        if vuln_type == "xss":
            template["tags"].extend(["xss", "injection", "web"])
            template["description"] = "Detects Cross-Site Scripting (XSS) vulnerabilities"
        elif vuln_type == "sqli":
            template["tags"].extend(["sqli", "injection", "database"])
            template["description"] = "Detects SQL Injection vulnerabilities"

        return template

    def _get_severity_for_vuln_type(self, vuln_type: str) -> str:
        """Get severity level for vulnerability type"""
        high_severity = ["sqli", "rce", "ssrf"]
        medium_severity = ["xss", "csrf", "lfi", "rfi"]

        if vuln_type in high_severity:
            return "high"
        elif vuln_type in medium_severity:
            return "medium"
        else:
            return "low"

    def _generate_yaml_content(self, vuln_type: str, template_id: str) -> str:
        """Generate actual YAML content for the nuclei template"""

        if vuln_type == "xss":
            return f'''id: {template_id}

info:
  name: XSS Detection Template
  author: OASM Assistant
  severity: medium
  description: Detects Cross-Site Scripting (XSS) vulnerabilities
  tags: xss,injection,web

requests:
  - method: GET
    path:
      - "{{{{BaseURL}}}}/search?q=<script>alert('XSS')</script>"
      - "{{{{BaseURL}}}}/index.php?page=<img src=x onerror=alert('XSS')>"

    matchers-condition: and
    matchers:
      - type: word
        words:
          - "<script>alert('XSS')</script>"
          - "<img src=x onerror=alert('XSS')>"
        part: body

      - type: word
        words:
          - "text/html"
        part: header

      - type: status
        status:
          - 200'''

        elif vuln_type == "sqli":
            return f'''id: {template_id}

info:
  name: SQL Injection Detection Template
  author: OASM Assistant
  severity: high
  description: Detects SQL Injection vulnerabilities
  tags: sqli,injection,database

requests:
  - method: GET
    path:
      - "{{{{BaseURL}}}}/login.php?id=1' OR '1'='1"
      - "{{{{BaseURL}}}}/search?q=1' UNION SELECT 1,2,3--"

    matchers-condition: and
    matchers:
      - type: word
        words:
          - "mysql_fetch"
          - "ORA-00933"
          - "Microsoft Access Driver"
          - "SQLServer JDBC Driver"
        part: body

      - type: status
        status:
          - 200
          - 500'''

        else:
            return f'''id: {template_id}

info:
  name: {vuln_type.title()} Detection Template
  author: OASM Assistant
  severity: medium
  description: Detects {vuln_type} vulnerabilities
  tags: {vuln_type},vulnerability

requests:
  - method: GET
    path:
      - "{{{{BaseURL}}}}"

    matchers:
      - type: status
        status:
          - 200'''