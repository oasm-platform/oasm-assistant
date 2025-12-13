"""Multi-agent security workflow orchestration using LangGraph"""

from typing import Dict, Any, List, Optional, TypedDict, AsyncGenerator

from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, END

from common.logger import logger
from agents.specialized import AnalysisAgent, OrchestrationAgent


class SecurityWorkflowState(TypedDict):
    """State container for security workflow execution"""
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
    """Orchestrates multi-agent security workflows with sync/streaming support"""

    def __init__(
        self,
        db_session: Optional[Any] = None,
        workspace_id: Optional[Any] = None,
        user_id: Optional[Any] = None
    ):
        self.db_session = db_session
        self.workspace_id = workspace_id
        self.user_id = user_id
        self.available_agents = {
            "analysis": AnalysisAgent,
            "orchestration": OrchestrationAgent
        }
        self.workflow_graph = self._build_workflow_graph()
        logger.debug(
            f"SecurityCoordinator initialized "
            f"(DB: {'enabled' if db_session else 'disabled'}, "
            f"MCP: workspace={workspace_id}, user={user_id})"
        )

    def _build_workflow_graph(self) -> StateGraph:
        """Build LangGraph workflow with routing logic"""
        workflow = StateGraph(SecurityWorkflowState)

        workflow.add_node("router", self._route_task)
        workflow.add_node("analysis", lambda s: self._execute_agent(s, "analysis", "analyze_vulnerabilities"))
        workflow.add_node("orchestration", lambda s: self._execute_agent(s, "orchestration", "coordinate_workflow"))
        workflow.add_node("result_formatter", self._format_results)

        workflow.set_entry_point("router")
        
        workflow.add_conditional_edges(
            "router",
            lambda state: state.get("next_action", "end"),
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
        """Execute security task through workflow (sync)"""
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
            logger.error(f"Workflow execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "task_type": task.get("type", "unknown")
            }

    def _route_task(self, state: SecurityWorkflowState) -> SecurityWorkflowState:
        """Route task based on task_type"""
        task_type = state["task_type"]
        
        if task_type in ["security_analysis", "forensic_analysis", "malware_analysis"]:
            state["next_action"] = "analysis"
        elif task_type == "workflow_coordination":
            state["next_action"] = "orchestration"
        else:
            state["next_action"] = "analysis"  # Default
        
        return state

    def _execute_agent(
        self,
        state: SecurityWorkflowState,
        agent_key: str,
        action: str
    ) -> SecurityWorkflowState:
        """Execute task with specified agent"""
        try:
            agent_class = self.available_agents.get(agent_key)
            if not agent_class:
                state["error"] = f"{agent_key} agent not available"
                return state

            # Create agent with context
            if agent_key in ["orchestration", "analysis"]:
                agent = agent_class(
                    db_session=self.db_session,
                    workspace_id=self.workspace_id,
                    user_id=self.user_id
                )
            else:
                agent = agent_class()

            # Prepare task payload
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

            logger.info(f"{agent_key} agent completed")

        except Exception as e:
            logger.error(f"{agent_key} agent failed: {e}")
            state["error"] = f"{agent_key} agent failed: {e}"

        return state

    def _format_results(self, state: SecurityWorkflowState) -> SecurityWorkflowState:
        """Format final results from agents"""
        try:
            state["final_result"] = {
                "task_type": state["task_type"],
                "question": state["question"],
                "target": state["target"],
                "agents_used": list(state["agent_results"].keys()),
                "results": state["agent_results"],
                "success": len(state["agent_results"]) > 0 and not state.get("error")
            }
            logger.info(f"Results formatted for {len(state['agent_results'])} agents")
        except Exception as e:
            logger.error(f"Result formatting failed: {e}")
            state["error"] = f"Result formatting failed: {e}"

        return state

    def process_message_question(self, question: str) -> str:
        """Process question and return formatted response (sync)"""
        try:
            result = self.execute_security_task({
                "type": "security_analysis",
                "question": question,
                "target": None,
                "vulnerability_data": {}
            })

            if result.get("success"):
                agent_results = result.get("agent_results", {})
                response = ""
                for agent_result in agent_results.values():
                    if isinstance(agent_result, dict) and "response" in agent_result:
                        response += agent_result['response']
                return response if response else "Analysis completed successfully."
            
            return f"I encountered difficulties processing your request: {result.get('error', 'Unknown error')}"
        
        except Exception as e:
            logger.error(f"Coordination error: {e}")
            return f"I'm experiencing technical difficulties: {str(e)}"

    async def process_message_question_streaming(
        self,
        question: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Process question with streaming events (async)"""
        try:
            yield {
                "type": "thinking",
                "agent": "SecurityCoordinator",
                "thought": "Analyzing security question and determining workflow",
                "roadmap": [
                    {"step": "1", "description": "Route to appropriate security agent"},
                    {"step": "2", "description": "Execute security analysis with LLM"},
                    {"step": "3", "description": "Stream response to user"}
                ]
            }

            agent_class = self.available_agents.get("analysis")
            if not agent_class:
                yield {
                    "type": "error",
                    "error": "Analysis agent not available",
                    "agent": "SecurityCoordinator"
                }
                return

            agent = agent_class(
                db_session=self.db_session,
                workspace_id=self.workspace_id,
                user_id=self.user_id
            )

            task = {
                "action": "analyze_vulnerabilities",
                "question": question,
                "target": None,
                "vulnerability_data": {}
            }

            async for event in agent.execute_task_streaming(task):
                yield event

        except Exception as e:
            logger.error(f"Streaming coordination error: {e}", exc_info=True)
            yield {
                "type": "error",
                "error_type": "StreamingCoordinationError",
                "error_message": str(e),
                "agent": "SecurityCoordinator"
            }
