from typing import Dict, Any, List
from datetime import datetime

from agents.core.base_agent import BaseAgent, AgentRole, AgentType, AgentCapability
from common.logger import logger


class OASMSecurityAgent(BaseAgent):
    """OASM Security Assistant Agent for comprehensive security Q&A"""

    def setup_tools(self) -> List[Any]:
        """Setup security tools for the assistant"""
        return [
            {"name": "threat_analyzer", "type": "analysis", "status": "ready"},
            {"name": "vulnerability_scanner", "type": "scanner", "status": "ready"},
            {"name": "security_advisor", "type": "advisory", "status": "ready"},
            {"name": "incident_responder", "type": "response", "status": "ready"}
        ]

    def create_prompt_template(self) -> str:
        """Create security-focused prompt template"""
        return self._create_security_prompt_template()

    def process_observation(self, observation: Any) -> Dict[str, Any]:
        """Process security observations"""
        return {
            "processed_at": datetime.utcnow(),
            "observation_type": type(observation).__name__,
            "security_relevance": self._assess_security_relevance(observation),
            "confidence": 0.8
        }

    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute security-related tasks"""
        task_type = task.get("action", "general_query")

        if task_type == "security_analysis":
            return self._perform_security_analysis(task)
        elif task_type == "threat_assessment":
            return self._perform_threat_assessment(task)
        elif task_type == "vulnerability_check":
            return self._perform_vulnerability_check(task)
        else:
            return self._handle_general_query(task)

    def _perform_security_analysis(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Perform comprehensive security analysis"""
        query = task.get("query", "")

        # Mock analysis for now - in production, this would use real security tools
        analysis_data = {
            "query": query,
            "security_context": "threat_landscape_analysis",
            "risk_indicators": ["potential_vulnerability", "threat_intelligence"],
            "recommended_actions": ["monitor", "investigate", "mitigate"]
        }

        # Use LLM for analysis if available
        if self.llm:
            analysis = self.analyze_with_llm(analysis_data, "security_analysis")
            return {
                "success": True,
                "analysis": analysis.get("response", "Analysis completed"),
                "confidence": analysis.get("confidence", 0.8),
                "risk_level": "medium"
            }
        else:
            return {
                "success": True,
                "analysis": "Based on your security analysis request, I recommend implementing comprehensive monitoring, conducting regular vulnerability assessments, and maintaining updated threat intelligence feeds. Key areas to focus on include network security, endpoint protection, and user access management.",
                "confidence": 0.7,
                "risk_level": "medium"
            }

    def _perform_threat_assessment(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Perform threat assessment and risk evaluation"""
        query = task.get("query", "")

        threat_data = {
            "query": query,
            "threat_indicators": ["suspicious_activity", "anomalous_behavior"],
            "attack_vectors": ["network", "application", "social_engineering"],
            "severity": "medium"
        }

        if self.llm:
            assessment = self.analyze_with_llm(threat_data, "threat_assessment")
            return {
                "success": True,
                "assessment": assessment.get("response", "Threat assessment completed"),
                "threat_level": "medium",
                "recommendations": ["implement_monitoring", "update_defenses"]
            }
        else:
            return {
                "success": True,
                "assessment": "Based on your threat assessment request, common threats include malware, phishing attacks, insider threats, and advanced persistent threats (APTs). I recommend implementing real-time monitoring, updating security controls, and conducting regular threat hunting activities. Key defenses include endpoint detection and response (EDR), network segmentation, and user education.",
                "threat_level": "medium",
                "recommendations": ["implement_monitoring", "update_defenses", "conduct_threat_hunting"]
            }

    def _perform_vulnerability_check(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Perform vulnerability assessment and scanning guidance"""
        query = task.get("query", "")

        vuln_data = {
            "query": query,
            "scan_type": "comprehensive",
            "target_systems": ["web_application", "network_infrastructure"],
            "known_vulnerabilities": ["CVE-2023-1234", "CVE-2023-5678"]
        }

        if self.llm:
            check_result = self.analyze_with_llm(vuln_data, "vulnerability_check")
            return {
                "success": True,
                "vulnerabilities": check_result.get("response", "Vulnerability check completed"),
                "severity": "high",
                "remediation": ["patch_systems", "update_configurations"]
            }
        else:
            return {
                "success": True,
                "vulnerabilities": "For vulnerability assessments, I recommend using tools like Nuclei for web application scanning, Nessus for comprehensive network scans, or OpenVAS for open-source vulnerability assessment. Common vulnerabilities to check include unpatched software, weak authentication, misconfigured services, and outdated encryption protocols. Regular patching and configuration reviews are essential.",
                "severity": "medium",
                "remediation": ["patch_systems", "update_configurations", "regular_scanning"]
            }

    def _handle_general_query(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Handle general security queries with expert knowledge"""
        query = task.get("query", "")

        if self.llm:
            # Create security-focused context for the query
            security_context = {
                "alert_level": self.state.security_alert_level.value,
                "active_threats": self.state.active_threats,
                "environment_state": self.environment.get_environment_state()
            }

            response = self.query_llm(query, context=security_context)
            return {
                "success": True,
                "answer": response,
                "confidence": 0.9,
                "query_type": "general_security"
            }
        else:
            # Enhanced fallback response for common security topics
            query_lower = query.lower()

            if "firewall" in query_lower:
                answer = "Firewalls are essential network security devices that monitor and control incoming and outgoing network traffic based on predetermined security rules. They act as a barrier between trusted internal networks and untrusted external networks. Key considerations include proper rule configuration, regular updates, integration with other security tools, and monitoring logs for suspicious activity."
            elif "malware" in query_lower:
                answer = "Malware protection requires a multi-layered approach including next-generation antivirus software, endpoint detection and response (EDR), email security gateways, web filtering, network segmentation, and comprehensive user education about social engineering attacks. Regular system updates and backups are also crucial."
            elif "password" in query_lower:
                answer = "Strong password practices include using unique, complex passwords for each account, enabling multi-factor authentication (MFA), using reputable password managers, avoiding password reuse, and following your organization's password policy requirements. Consider implementing passwordless authentication where possible."
            elif "encryption" in query_lower:
                answer = "Encryption is crucial for protecting data in transit and at rest. Use strong algorithms like AES-256 for data at rest and TLS 1.3 for data in transit. Implement proper key management practices, ensure encryption for all sensitive communications and storage, and regularly review encryption policies."
            elif "backup" in query_lower:
                answer = "Effective backup strategies follow the 3-2-1 rule: 3 copies of data, 2 different storage types, and 1 offsite location. Regular testing of restore procedures is essential for business continuity. Consider immutable backups to protect against ransomware attacks."
            elif "incident" in query_lower:
                answer = "Incident response involves preparation, identification, containment, eradication, recovery, and lessons learned. Key steps include having an incident response plan, designated response team, communication procedures, forensic capabilities, and regular tabletop exercises to test preparedness."
            elif "vulnerability" in query_lower:
                answer = "Vulnerability management includes regular scanning with tools like Nuclei, Nessus, or OpenVAS, prioritizing based on CVSS scores and business impact, implementing patches promptly, and maintaining an asset inventory. Consider automated scanning and integration with security orchestration platforms."
            elif "threat" in query_lower or "attack" in query_lower:
                answer = "Threat mitigation requires understanding your threat landscape, implementing defense-in-depth strategies, monitoring for indicators of compromise (IOCs), and maintaining current threat intelligence. Key defenses include network segmentation, endpoint protection, email security, and user awareness training."
            else:
                answer = f"Thank you for your security question: '{query}'. For comprehensive security guidance, I recommend consulting with security professionals and following industry frameworks like NIST Cybersecurity Framework, ISO 27001, or CIS Controls. These provide structured approaches to managing cybersecurity risks."

            return {
                "success": True,
                "answer": answer,
                "confidence": 0.7,
                "query_type": "fallback"
            }

    def _assess_security_relevance(self, observation: Any) -> str:
        """Assess security relevance of an observation"""
        obs_str = str(observation).lower()
        security_keywords = ["threat", "vulnerability", "attack", "security", "malware", "breach"]

        for keyword in security_keywords:
            if keyword in obs_str:
                return "high"
        return "medium"

    def answer_security_question(self, question: str) -> Dict[str, Any]:
        """Main method to answer security questions with intelligent routing"""
        logger.info(f"Processing security question: {question[:100]}...")

        # Determine question type and create appropriate task
        question_lower = question.lower()

        if any(word in question_lower for word in ["threat", "attack", "malicious"]):
            task = {
                "action": "threat_assessment",
                "query": question,
                "priority": "high"
            }
        elif any(word in question_lower for word in ["vulnerability", "cve", "exploit"]):
            task = {
                "action": "vulnerability_check",
                "query": question,
                "priority": "high"
            }
        elif any(word in question_lower for word in ["analyze", "assessment", "security analysis"]):
            task = {
                "action": "security_analysis",
                "query": question,
                "priority": "medium"
            }
        else:
            task = {
                "action": "general_query",
                "query": question,
                "priority": "normal"
            }

        # Execute the task
        result = self.execute_task(task)

        # Format the response
        if result.get("success"):
            answer = result.get("answer") or result.get("analysis") or result.get("assessment") or result.get("vulnerabilities")
            confidence = result.get("confidence", 0.8)

            # Add security context to the answer
            formatted_answer = f"{answer}\n\n**Security Context:**\n"
            formatted_answer += f"- Query Type: {task['action']}\n"
            formatted_answer += f"- Confidence Level: {confidence:.2f}\n"
            formatted_answer += f"- Alert Level: {self.state.security_alert_level.value}\n"

            if result.get("recommendations"):
                formatted_answer += f"- Recommendations: {', '.join(result['recommendations'])}\n"

            return {
                "success": True,
                "answer": formatted_answer,
                "confidence": confidence,
                "metadata": {
                    "task_type": task["action"],
                    "alert_level": self.state.security_alert_level.value,
                    "processing_time": datetime.utcnow().isoformat()
                }
            }
        else:
            return {
                "success": False,
                "answer": "I encountered an issue processing your security question. Please try rephrasing or contact support.",
                "confidence": 0.0,
                "metadata": {
                    "error": result.get("error", "Unknown error"),
                    "processing_time": datetime.utcnow().isoformat()
                }
            }


def create_security_agent() -> OASMSecurityAgent:
    """Factory function to create and configure OASM Security Agent"""
    capabilities = [
        AgentCapability(
            name="security_analysis",
            description="Analyze security threats and vulnerabilities",
            tools=["threat_analyzer", "vulnerability_scanner"]
        ),
        AgentCapability(
            name="incident_response",
            description="Provide incident response guidance",
            tools=["incident_responder"]
        ),
        AgentCapability(
            name="security_advisory",
            description="Provide security best practices and recommendations",
            tools=["security_advisor"]
        )
    ]

    try:
        agent = OASMSecurityAgent(
            name="OASM_Security_Assistant",
            role=AgentRole.SECURITY_RESEARCHER,
            agent_type=AgentType.GOAL_BASED,
            capabilities=capabilities
            # Let the agent use the configured LLM from config
        )
        logger.info("OASM Security Agent created successfully")
        return agent
    except Exception as e:
        logger.error(f"Failed to create OASM Security Agent: {e}")
        raise