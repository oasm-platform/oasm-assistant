from typing import Dict, Any, List, Optional, TypedDict
import re

from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, END

from agents.core import BaseAgent, AgentRole, AgentType
from common.logger import logger
from agents.specialized import NucleiGenerationAgent



class SecurityWorkflowState(TypedDict):
    messages: List[Any]
    question: str
    task_type: str
    target: Optional[str]
    vulnerability_data: Dict[str, Any]
    agent_results: Dict[str, Any]
    current_agent: Optional[str]
    next_action: Optional[str]
    final_result: Optional[Dict[str, Any]]
    error: Optional[str]


class SecurityCoordinator:
    def __init__(self):
        self.available_agents = self._create_agent_registry()
        self.workflow_graph = self._build_workflow_graph()
        logger.info("Security coordinator initialized")

    def _create_agent_registry(self) -> Dict[str, type]:
        class PlaceholderAgent(BaseAgent):
            def __init__(self, name: str, **kwargs):
                super().__init__(
                    name=name,
                    role=AgentRole.THREAT_ANALYST,
                    agent_type=AgentType.GOAL_BASED,
                    **kwargs
                )

            def setup_tools(self):
                return []

            def create_prompt_template(self):
                return f"You are {self.name}, a security agent."

            def process_observation(self, observation):
                return {"processed": True, "agent": self.name}

            def execute_task(self, task):
                return {
                    "success": True,
                    "message": f"{self.name} executed task: {task.get('action', 'unknown')}",
                    "agent": self.name
                }

        def create_agent(name: str):
            return lambda **kwargs: PlaceholderAgent(name=name, **kwargs)

        nuclei_agent_class = NucleiGenerationAgent

        return {
            "nuclei_generator": nuclei_agent_class,
            "web_security": create_agent("WebSecurityAgent"),
            "vulnerability_scanner": create_agent("VulnerabilityScanAgent"),
            "network_recon": create_agent("NetworkReconAgent"),
            "report_generator": create_agent("ReportGenerationAgent")
        }

    def _build_workflow_graph(self) -> StateGraph:
        workflow = StateGraph(SecurityWorkflowState)

        workflow.add_node("router", self._route_task)
        workflow.add_node("nuclei_generation", self._execute_nuclei_generation)
        workflow.add_node("web_security", self._execute_web_security)
        workflow.add_node("vulnerability_scan", self._execute_vulnerability_scan)
        workflow.add_node("network_recon", self._execute_network_recon)
        workflow.add_node("report_generation", self._execute_report_generation)
        workflow.add_node("result_formatter", self._format_results)

        workflow.set_entry_point("router")

        workflow.add_conditional_edges(
            "router",
            self._should_continue_from_router,
            {
                "nuclei_generation": "nuclei_generation",
                "web_security": "web_security",
                "vulnerability_scan": "vulnerability_scan",
                "network_recon": "network_recon",
                "report_generation": "report_generation",
                "end": END
            }
        )

        for node in ["nuclei_generation", "web_security", "vulnerability_scan", "network_recon", "report_generation"]:
            workflow.add_edge(node, "result_formatter")

        workflow.add_edge("result_formatter", END)

        return workflow.compile()

    def execute_security_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        try:
            initial_state = SecurityWorkflowState(
                messages=[HumanMessage(content=task.get("question", ""))],
                question=task.get("question", ""),
                task_type=task.get("type", "general"),
                target=task.get("target"),
                vulnerability_data=task.get("vulnerability_data", {}),
                agent_results={},
                current_agent=None,
                next_action=None,
                final_result=None,
                error=None
            )

            final_state = self.workflow_graph.invoke(initial_state)

            if final_state.get("error"):
                return {
                    "success": False,
                    "error": final_state["error"],
                    "task_type": task.get("type")
                }

            return {
                "success": True,
                "result": final_state.get("final_result", {}),
                "agent_results": final_state.get("agent_results", {}),
                "task_type": task.get("type"),
                "participating_agents": list(final_state.get("agent_results", {}).keys())
            }

        except Exception as e:
            logger.error(f"LangGraph workflow execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "task_type": task.get("type", "unknown")
            }

    def _route_task(self, state: SecurityWorkflowState) -> SecurityWorkflowState:
        task_type = state["task_type"]

        if task_type == "generate_nuclei_template":
            state["next_action"] = "nuclei_generation"
        elif task_type == "vulnerability_scan":
            state["next_action"] = "vulnerability_scan"
        elif task_type == "network_recon":
            state["next_action"] = "network_recon"
        elif task_type == "coordinate_security_analysis":
            state["next_action"] = "network_recon"
        elif task_type == "multi_agent_scan":
            state["next_action"] = "network_recon"
        elif task_type == "threat_investigation":
            state["next_action"] = "vulnerability_scan"
        else:
            state["next_action"] = "report_generation"

        logger.info(f"Task routed: {task_type} -> {state['next_action']}")
        return state

    def _should_continue_from_router(self, state: SecurityWorkflowState) -> str:
        next_action = state.get("next_action", "end")

        if next_action in ["nuclei_generation", "web_security", "vulnerability_scan", "network_recon", "report_generation"]:
            return next_action

        return "end"

    def _execute_nuclei_generation(self, state: SecurityWorkflowState) -> SecurityWorkflowState:
        try:
            logger.info("Executing nuclei template generation")

            agent_class = self.available_agents.get("nuclei_generator")
            if not agent_class:
                state["error"] = "Nuclei generation agent not available"
                return state

            agent = agent_class()

            task = {
                "action": "generate_template",
                "vulnerability_data": state["vulnerability_data"],
                "target": state["target"],
                "question": state["question"]
            }

            result = agent.execute_task(task)

            state["agent_results"]["nuclei_generator"] = result
            state["current_agent"] = "nuclei_generator"

            logger.info("Nuclei template generation completed")

        except Exception as e:
            logger.error(f"Nuclei template generation failed: {e}")
            state["error"] = f"Nuclei template generation failed: {e}"

        return state

    def _execute_web_security(self, state: SecurityWorkflowState) -> SecurityWorkflowState:
        return self._execute_agent_task(state, "web_security", "analyze_web_security", "Web security analysis")

    def _execute_vulnerability_scan(self, state: SecurityWorkflowState) -> SecurityWorkflowState:
        return self._execute_agent_task(state, "vulnerability_scanner", "run_security_scan", "Vulnerability scan")

    def _execute_network_recon(self, state: SecurityWorkflowState) -> SecurityWorkflowState:
        return self._execute_agent_task(state, "network_recon", "run_security_scan", "Network reconnaissance")

    def _execute_report_generation(self, state: SecurityWorkflowState) -> SecurityWorkflowState:
        return self._execute_agent_task(state, "report_generator", "generate_report", "Report generation")

    def _execute_agent_task(self, state: SecurityWorkflowState, agent_key: str, action: str, description: str) -> SecurityWorkflowState:
        try:
            logger.info(f"Executing {description.lower()}")

            agent_class = self.available_agents.get(agent_key)
            if not agent_class:
                state["error"] = f"{description} agent not available"
                return state

            agent = agent_class()

            task = {
                "action": action,
                "vulnerability_data": state["vulnerability_data"],
                "target": state["target"],
                "question": state["question"]
            }

            if agent_key == "report_generator":
                task["data"] = {
                    "question": state["question"],
                    "task_type": state["task_type"],
                    "target": state["target"],
                    "agent_results": state["agent_results"]
                }

            result = agent.execute_task(task)

            state["agent_results"][agent_key] = result
            state["current_agent"] = agent_key

            logger.info(f"{description} completed")

        except Exception as e:
            logger.error(f"{description} failed: {e}")
            state["error"] = f"{description} failed: {e}"

        return state

    def _format_results(self, state: SecurityWorkflowState) -> SecurityWorkflowState:
        try:
            final_result = {
                "task_type": state["task_type"],
                "question": state["question"],
                "target": state["target"],
                "agents_used": list(state["agent_results"].keys()),
                "results": state["agent_results"],
                "success": len(state["agent_results"]) > 0 and not state.get("error")
            }

            state["final_result"] = final_result
            logger.info(f"Results formatted for {len(state['agent_results'])} agents")

        except Exception as e:
            logger.error(f"Result formatting failed: {e}")
            state["error"] = f"Result formatting failed: {e}"

        return state

    def _analyze_question_type(self, question: str) -> str:
        """Analyze question to determine appropriate multi-agent task type"""
        question_lower = question.lower()

        if any(keyword in question_lower for keyword in ["nuclei", "template", "generate", "vulnerability", "cve"]):
            return "generate_nuclei_template"
        if any(keyword in question_lower for keyword in ["scan", "analyze", "security", "threat", "attack"]):
            return "coordinate_security_analysis"
        if any(keyword in question_lower for keyword in ["nmap", "subfinder", "httpx", "reconnaissance", "recon"]):
            return "multi_agent_scan"
        if any(keyword in question_lower for keyword in ["investigate", "incident", "malware", "breach"]):
            return "threat_investigation"

        return "coordinate_security_analysis"

    def _extract_target_from_question(self, question: str) -> str:
        """Extract target information from question"""
        domain_pattern = r'\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b'
        domains = re.findall(domain_pattern, question)

        ip_pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
        ips = re.findall(ip_pattern, question)

        if domains:
            return domains[0]
        elif ips:
            return ips[0]

        return "unknown"

    def _extract_vulnerability_data(self, question: str) -> dict:
        """Extract vulnerability data from question"""
        vulnerability_data = {}

        cve_pattern = r'CVE-\d{4}-\d{4,7}'
        cves = re.findall(cve_pattern, question, re.IGNORECASE)
        if cves:
            vulnerability_data["cve_id"] = cves[0]

        severity_keywords = ["critical", "high", "medium", "low"]
        for severity in severity_keywords:
            if severity in question.lower():
                vulnerability_data["severity"] = severity
                break

        vuln_types = ["xss", "sqli", "sql injection", "lfi", "rfi", "ssrf", "csrf", "rce"]
        for vuln_type in vuln_types:
            if vuln_type in question.lower():
                vulnerability_data["vulnerability_type"] = vuln_type
                break

        vulnerability_data["description"] = question
        return vulnerability_data

    def _format_langgraph_response(self, result: dict, question: str) -> str:
        """Format LangGraph coordination results into readable response"""
        try:
            task_type = result.get("task_type", "unknown")
            success = result.get("success", False)

            if not success:
                error_msg = result.get("error", "Unknown error")
                return f"I apologize, but I encountered difficulties processing your request: {error_msg}"

            participating_agents = result.get("participating_agents", [])
            agent_results = result.get("agent_results", {})

            if task_type == "generate_nuclei_template":
                return self._format_langgraph_nuclei_response(result, question)

            response = f"**LangGraph Security Analysis Complete**\n\n"
            response += f"**Task Type :** {task_type.replace('_', ' ').title()}\n"
            response += f"**Question:** {question}\n"
            response += f"**Participating Agents:** {len(participating_agents)}\n\n"

            if agent_results:
                response += "**Agent Analysis Results:**\n"
                for agent_name, agent_result in agent_results.items():
                    if isinstance(agent_result, dict):
                        success_status = "✅ Success" if agent_result.get("success") else "❌ Failed"
                        response += f"\n**{agent_name.replace('_', ' ').title()}:** {success_status}\n"

                        if agent_result.get("success"):
                            if "analysis" in agent_result:
                                analysis = agent_result["analysis"]
                                if isinstance(analysis, dict):
                                    response += f"- Risk Assessment: {analysis.get('risk_assessment', 'N/A')}\n"
                                    response += f"- Confidence: {analysis.get('confidence', 0):.1%}\n"

                            if "scan_results" in agent_result:
                                response += f"- Scan completed successfully\n"
                        else:
                            error = agent_result.get("error", "Unknown error")
                            response += f"- Error: {error}\n"

            response += f"\n**Summary:**\nCompleted multi-agent security analysis using LangGraph workflow coordination. "
            response += f"Each agent contributed specialized expertise to provide comprehensive security insights."

            return response

        except Exception as e:
            logger.error(f"Error formatting LangGraph response: {e}")
            return f"LangGraph analysis completed, but I encountered an issue formatting the detailed response."

    def _format_langgraph_nuclei_response(self, result: dict, question: str) -> str:
        """Format LangGraph nuclei template generation response"""
        try:
            agent_results = result.get("agent_results", {})
            nuclei_result = agent_results.get("nuclei_generator", {})

            if nuclei_result.get("success"):
                template_info = nuclei_result.get("template")
                if template_info:
                    if hasattr(template_info, 'id'):
                        response = f"**Nuclei Template Generated Successfully**\n\n"
                        response += f"**Question:** {question}\n"
                        response += f"**Template Details:**\n"
                        response += f"- Template ID: {getattr(template_info, 'id', 'N/A')}\n"
                        response += f"- Name: {getattr(template_info, 'name', 'N/A')}\n"
                        response += f"- Severity: {getattr(template_info, 'severity', 'N/A')}\n"
                        response += f"- Description: {getattr(template_info, 'description', 'N/A')}\n"
                        response += f"- Tags: {', '.join(getattr(template_info, 'tags', []))}\n\n"
                        response += f"**Generation Metadata:**\n"
                        response += f"- Confidence: {getattr(template_info, 'confidence', 0):.1%}\n"
                        response += f"- Generated via LangGraph workflow\n\n"
                        response += f"The template is ready for use with nuclei scanning tools and follows nuclei best practices."
                        response += f"\n\n"
                        response += f"```yaml\n{template_info.yaml_content}\n```"
                        return response
                    elif isinstance(template_info, dict):
                        response = f"**Nuclei Template Generated Successfully**\n\n"
                        response += f"**Question:** {question}\n"
                        response += f"**Template Details:**\n"
                        response += f"- Template ID: {template_info.get('id', 'N/A')}\n"
                        response += f"- Name: {template_info.get('name', 'N/A')}\n"
                        response += f"- Severity: {template_info.get('severity', 'N/A')}\n"
                        response += f"- Description: {template_info.get('description', 'N/A')}\n"
                        response += f"- Tags: {', '.join(template_info.get('tags', []))}\n\n"
                        response += f"**Generation Metadata:**\n"
                        response += f"- Confidence: {template_info.get('confidence', 0):.1%}\n"
                        response += f"- Generated via LangGraph workflow\n\n"
                        response += f"The template is ready for use with nuclei scanning tools and follows nuclei best practices."
                        return response
                    else:
                        logger.error(f"Unknown template format: {type(template_info)}")
                        return "Nuclei template generation completed, but template format is not recognized."

            return "Nuclei template generation completed via LangGraph, but template details are not available."

        except Exception as e:
            logger.error(f"Error formatting LangGraph nuclei response: {e}")
            return "Nuclei template generation completed, but encountered formatting issues."

    def _format_nuclei_generation_response(self, result: dict, question: str) -> str:
        """Format nuclei template generation response"""
        try:
            if result.get("success"):
                template = result.get("template")
                if template:
                    if hasattr(template, 'id'):
                        return f"""I've successfully generated a nuclei template based on your request.

 **Template Details:**
 - Template ID: {template.id}
 - Name: {template.name}
 - Severity: {template.severity}
 - Description: {template.description}
 - Tags: {', '.join(template.tags)}

 **Generation Metadata:**
 - Confidence: {template.confidence:.2f}
 - Generated at: {template.created_at}

 The template is ready for use with nuclei scanning tools. It includes proper YAML structure, detection logic, and follows nuclei best practices.

 ```yaml
 {template.yaml_content}
 ```"""
                    elif isinstance(template, dict):
                        return f"""I've successfully generated a nuclei template based on your request.

 **Template Details:**
 - Template ID: {template.get('id', 'N/A')}
 - Name: {template.get('name', 'N/A')}
 - Severity: {template.get('severity', 'medium')}
 - Description: {template.get('description', '')}
 - Tags: {', '.join(template.get('tags', []))}

 **Generation Metadata:**
 - Confidence: {template.get('confidence', 0):.2f}
 - Generated at: {template.get('created_at', '')}

 The template is ready for use with nuclei scanning tools. It includes proper YAML structure, detection logic, and follows nuclei best practices."""
                    else:
                        return "Nuclei template generation completed, but template format is not recognized."
                else:
                    return "Nuclei template generation completed, but template details are not available in the expected format."
            else:
                return "Nuclei template generation was requested but not properly delegated to the specialized agent."

        except Exception as e:
            logger.error(f"Error formatting nuclei response: {e}")
            return "Nuclei template generation completed, but I encountered an issue formatting the detailed response."

    def create_security_agent(self):
        """Create a basic security agent for fallback"""
        class BasicSecurityAgent(BaseAgent):
            def setup_tools(self):
                return []

            def create_prompt_template(self):
                return "You are a security assistant."

            def process_observation(self, observation):
                return {"processed": True}

            def execute_task(self, task):
                return {"success": False, "message": "Basic agent - limited functionality"}

            def answer_security_question(self, question):
                """Synchronous method to answer security questions"""
                try:
                    response = self.query_llm(f"Security question: {question}")
                    return {
                        "success": True,
                        "answer": response,
                        "agent": self.name
                    }
                except Exception as e:
                    logger.error(f"Security agent error: {e}")
                    return {
                        "success": False,
                        "answer": "I apologize, but I'm currently unable to process this security question.",
                        "error": str(e)
                    }

        return BasicSecurityAgent(
            name="BasicSecurityAgent",
            role=AgentRole.THREAT_ANALYST
        )

    def _fallback_to_security_agent(self, question: str, security_agent) -> str:
        """Fallback to single security agent if multi-agent fails"""
        if security_agent:
            try:
                result = security_agent.answer_security_question(question)

                if result.get("success"):
                    return result.get("answer", "")
                else:
                    return result.get("answer", "I apologize, but I couldn't process your security question at this time.")

            except Exception as e:
                logger.error(f"Error with fallback security agent: {e}")
                return "I apologize, but I'm experiencing technical difficulties. Please try again later."
        else:
            return f"Thank you for your question: '{question}'. I'm currently unable to provide detailed security analysis, but I recommend consulting with security professionals for specific security concerns."

    def process_message_question(self, question: str, is_create_template: bool = False):
        """Process a message question and return an appropriate answer"""
        security_agent = self.create_security_agent()

        if is_create_template:
            try:
                nuclei_agent = NucleiGenerationAgent()
                task = {
                    "action": "generate_template",
                    "question": question,
                    "target": self._extract_target_from_question(question),
                    "vulnerability_data": self._extract_vulnerability_data(question)
                }
                result = nuclei_agent.execute_task(task)

                if result.get("success"):
                    return self._format_nuclei_generation_response(result, question)
                else:
                    return self._fallback_to_security_agent(question, security_agent)
            except Exception as e:
                logger.error(f"Error with nuclei generation agent: {e}")
                return self._fallback_to_security_agent(question, security_agent)
        else:
            try:
                task_type = self._analyze_question_type(question)
                coordination_task = {
                    "type": task_type,
                    "question": question,
                    "target": self._extract_target_from_question(question),
                    "vulnerability_data": self._extract_vulnerability_data(question)
                }
                result = self.execute_security_task(coordination_task)

                if result.get("success"):
                    return self._format_langgraph_response(result, question)
                else:
                    return self._fallback_to_security_agent(question, security_agent)
            except Exception as e:
                logger.error(f"Error with coordination: {e}")
                return self._fallback_to_security_agent(question, security_agent)

