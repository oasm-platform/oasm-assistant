from typing import Dict, Any, List, Optional, TypedDict, TYPE_CHECKING
import re

from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, END

from agents.core import BaseAgent, AgentRole, AgentType
from common.logger import logger
from agents.specialized import (
    AnalysisAgent,
    OrchestrationAgent
)

if TYPE_CHECKING:
    from tools.mcp_client import MCPManager



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
    def __init__(
        self,
        db_session: Optional[Any] = None,
        workspace_id: Optional[Any] = None,
        user_id: Optional[Any] = None
    ):
        """
        Initialize Security Coordinator

        Args:
            db_session: Database session for agents
            workspace_id: Workspace ID for MCP integration (optional)
            user_id: User ID for MCP integration (optional)
        """
        self.db_session = db_session
        self.workspace_id = workspace_id
        self.user_id = user_id
        self.available_agents = self._create_agent_registry()
        self.workflow_graph = self._build_workflow_graph()
        logger.info(f"Security coordinator initialized (DB: {'enabled' if db_session else 'disabled'}, MCP context: workspace={workspace_id}, user={user_id})")

    def _create_agent_registry(self) -> Dict[str, type]:
        """Create registry of available security agents"""
        return {
            "analysis": AnalysisAgent,
            "orchestration": OrchestrationAgent
        }

    def _build_workflow_graph(self) -> StateGraph:
        workflow = StateGraph(SecurityWorkflowState)

        workflow.add_node("router", self._route_task)
        workflow.add_node("analysis", self._execute_analysis)
        workflow.add_node("orchestration", self._execute_orchestration)
        workflow.add_node("result_formatter", self._format_results)

        workflow.set_entry_point("router")

        workflow.add_conditional_edges(
            "router",
            self._should_continue_from_router,
            {
                "analysis": "analysis",
                "orchestration": "orchestration",
                "end": END
            }
        )

        for node in ["analysis", "orchestration"]:
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

        if task_type in ["security_analysis", "forensic_analysis", "malware_analysis"]:
            state["next_action"] = "analysis"
        elif task_type == "workflow_coordination":
            state["next_action"] = "orchestration"
        else:
            # Default to analysis for most security tasks
            state["next_action"] = "analysis"

        logger.info(f"Task routed: {task_type} -> {state['next_action']}")
        return state

    def _should_continue_from_router(self, state: SecurityWorkflowState) -> str:
        next_action = state.get("next_action", "end")

        if next_action in ["analysis", "orchestration"]:
            return next_action

        return "end"

    def _execute_analysis(self, state: SecurityWorkflowState) -> SecurityWorkflowState:
        return self._execute_agent_task(state, "analysis", "analyze_vulnerabilities", "Security analysis")

    def _execute_orchestration(self, state: SecurityWorkflowState) -> SecurityWorkflowState:
        return self._execute_agent_task(state, "orchestration", "coordinate_workflow", "Workflow orchestration")

    def _execute_agent_task(self, state: SecurityWorkflowState, agent_key: str, action: str, description: str) -> SecurityWorkflowState:
        try:
            logger.info(f"Executing {description.lower()}")

            agent_class = self.available_agents.get(agent_key)
            if not agent_class:
                state["error"] = f"{description} agent not available"
                return state

            # Create agent with appropriate parameters
            if agent_key == "orchestration":
                # OrchestrationAgent needs db_session, workspace_id, user_id
                agent = agent_class(
                    db_session=self.db_session,
                    workspace_id=self.workspace_id,
                    user_id=self.user_id
                )
            elif agent_key == "analysis":
                # AnalysisAgent creates MCP manager internally if workspace/user provided
                agent = agent_class(
                    db_session=self.db_session,
                    workspace_id=self.workspace_id,
                    user_id=self.user_id
                )
            else:
                # Other agents don't need special parameters yet
                agent = agent_class()

            task = {
                "action": action,
                "vulnerability_data": state["vulnerability_data"],
                "target": state["target"],
                "question": state["question"]
            }

            if agent_key == "orchestration":
                task["workflow"] = {
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
        """Analyze question to determine appropriate agent task type"""
        question_lower = question.lower()

        # Check for workflow coordination keywords
        if any(keyword in question_lower for keyword in ["coordinate", "workflow", "orchestrate", "manage"]):
            return "workflow_coordination"

        # Default to security analysis for all other tasks
        return "security_analysis"

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

            response = ""
            if agent_results:
                for agent_name, agent_result in agent_results.items():
                    if isinstance(agent_result, dict):
                        # If AnalysisAgent returns a response directly, use it
                        if agent_result.get("success") and "response" in agent_result:
                            response += f"\n{agent_result['response']}\n"
                        else:
                            # Fallback to old format for other agents
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

            return response

        except Exception as e:
            logger.error(f"Error formatting LangGraph response: {e}")
            return f"LangGraph analysis completed, but I encountered an issue formatting the detailed response."

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
            role=AgentRole.THREAT_INTELLIGENCE_AGENT
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

    def process_message_question(self, question: str):
        """Process a message question and return an appropriate answer"""
        security_agent = self.create_security_agent()

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

