from typing import Dict, Any, List, Optional, TypedDict

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


class LangGraphSecurityCoordinator:
    def __init__(self):
        self.available_agents = self._create_agent_registry()
        self.workflow_graph = self._build_workflow_graph()
        logger.info("LangGraph security coordinator initialized")

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


security_coordinator = LangGraphSecurityCoordinator()