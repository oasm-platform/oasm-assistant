"""
Security Coordinator Module

This module implements the SecurityCoordinator class which orchestrates
multi-agent security workflows using LangGraph for workflow management
and supports both synchronous and streaming response modes.
"""

from typing import Dict, Any, List, Optional, TypedDict, AsyncGenerator
import time
import asyncio

from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, END

from common.logger import logger
from agents.specialized import (
    AnalysisAgent,
    OrchestrationAgent
)


class SecurityWorkflowState(TypedDict):
    """State type for security workflow"""
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
    """
    Orchestrates multi-agent security workflows using LangGraph.

    This coordinator manages the execution of security analysis tasks by routing
    requests to appropriate specialized agents and handling both synchronous and
    streaming response modes with LLM-level streaming (like ChatGPT/Claude).
    """

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
        logger.info(
            f"Security coordinator initialized "
            f"(DB: {'enabled' if db_session else 'disabled'}, "
            f"MCP context: workspace={workspace_id}, user={user_id})"
        )

    def _create_agent_registry(self) -> Dict[str, type]:
        """Create registry of available security agents"""
        return {
            "analysis": AnalysisAgent,
            "orchestration": OrchestrationAgent
        }

    def _build_workflow_graph(self) -> StateGraph:
        """Build LangGraph workflow for security tasks"""
        workflow = StateGraph(SecurityWorkflowState)

        # Add workflow nodes
        workflow.add_node("router", self._route_task)
        workflow.add_node("analysis", self._execute_analysis)
        workflow.add_node("orchestration", self._execute_orchestration)
        workflow.add_node("result_formatter", self._format_results)

        # Set entry point
        workflow.set_entry_point("router")

        # Add conditional routing from router
        workflow.add_conditional_edges(
            "router",
            self._should_continue_from_router,
            {
                "analysis": "analysis",
                "orchestration": "orchestration",
                "end": END
            }
        )

        # Connect agent nodes to formatter
        for node in ["analysis", "orchestration"]:
            workflow.add_edge(node, "result_formatter")

        # Connect formatter to end
        workflow.add_edge("result_formatter", END)

        return workflow.compile()

    def execute_security_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a security task through the LangGraph workflow (synchronous)

        Args:
            task: Task dictionary containing question, type, target, and vulnerability data

        Returns:
            Result dictionary with success status and agent results
        """
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
        """Route task to appropriate agent based on task type"""
        task_type = state["task_type"]

        if task_type in ["security_analysis", "forensic_analysis", "malware_analysis"]:
            state["next_action"] = "analysis"
        elif task_type == "workflow_coordination":
            state["next_action"] = "orchestration"
        else:
            # Default to analysis for most security tasks
            state["next_action"] = "analysis"
        return state

    def _should_continue_from_router(self, state: SecurityWorkflowState) -> str:
        """Determine next workflow step from router"""
        next_action = state.get("next_action", "end")

        if next_action in ["analysis", "orchestration"]:
            return next_action

        return "end"

    def _execute_analysis(self, state: SecurityWorkflowState) -> SecurityWorkflowState:
        """Execute security analysis agent"""
        return self._execute_agent_task(
            state, "analysis", "analyze_vulnerabilities", "Security analysis"
        )

    def _execute_orchestration(self, state: SecurityWorkflowState) -> SecurityWorkflowState:
        """Execute workflow orchestration agent"""
        return self._execute_agent_task(
            state, "orchestration", "coordinate_workflow", "Workflow orchestration"
        )

    def _execute_agent_task(
        self,
        state: SecurityWorkflowState,
        agent_key: str,
        action: str,
        description: str
    ) -> SecurityWorkflowState:
        """
        Execute a task with a specific agent

        Args:
            state: Current workflow state
            agent_key: Key to identify agent in registry
            action: Action to perform
            description: Human-readable description for logging

        Returns:
            Updated workflow state
        """
        try:
            logger.info(f"Executing {description.lower()}")

            agent_class = self.available_agents.get(agent_key)
            if not agent_class:
                state["error"] = f"{description} agent not available"
                return state

            # Create agent with appropriate parameters
            if agent_key in ["orchestration", "analysis"]:
                agent = agent_class(
                    db_session=self.db_session,
                    workspace_id=self.workspace_id,
                    user_id=self.user_id
                )
            else:
                agent = agent_class()

            # Prepare task
            task = {
                "action": action,
                "vulnerability_data": state["vulnerability_data"],
                "target": state["target"],
                "question": state["question"]
            }

            # Add workflow context for orchestration agent
            if agent_key == "orchestration":
                task["workflow"] = {
                    "question": state["question"],
                    "task_type": state["task_type"],
                    "target": state["target"],
                    "agent_results": state["agent_results"]
                }

            # Execute task
            result = agent.execute_task(task)

            # Update state
            state["agent_results"][agent_key] = result
            state["current_agent"] = agent_key

            logger.info(f"{description} completed")

        except Exception as e:
            logger.error(f"{description} failed: {e}")
            state["error"] = f"{description} failed: {e}"

        return state

    def _format_results(self, state: SecurityWorkflowState) -> SecurityWorkflowState:
        """Format final results from all agents"""
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

    def process_message_question(self, question: str) -> str:
        """
        Process a message question and return an appropriate answer (synchronous)

        Args:
            question: The security question to process

        Returns:
            Formatted response string
        """
        try:
            coordination_task = {
                "type": "security_analysis",
                "question": question,
                "target": None,
                "vulnerability_data": {}
            }
            result = self.execute_security_task(coordination_task)

            if result.get("success"):
                return self._format_response(result)
            else:
                error_msg = result.get("error", "Unknown error")
                return f"I apologize, but I encountered difficulties processing your request: {error_msg}"
        except Exception as e:
            logger.error(f"Error with coordination: {e}")
            return f"I apologize, but I'm experiencing technical difficulties: {str(e)}"

    def _format_response(self, result: Dict[str, Any]) -> str:
        """Format result into readable response"""
        try:
            agent_results = result.get("agent_results", {})

            response = ""
            if agent_results:
                for agent_name, agent_result in agent_results.items():
                    if isinstance(agent_result, dict) and "response" in agent_result:
                        response += agent_result['response']

            return response if response else "Analysis completed successfully."

        except Exception as e:
            logger.error(f"Error formatting response: {e}")
            return "Analysis completed, but encountered an issue formatting the response."

    async def process_message_question_streaming(
        self,
        question: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process a message question and yield streaming events (like ChatGPT/Claude)

        Args:
            question: The security question to process

        Yields:
            Dict[str, Any]: Streaming events:
                - {"type": "thinking", "thought": str, "agent": str}
                - {"type": "tool_start", "tool_name": str, "agent": str}
                - {"type": "tool_output", "output": Any, "agent": str}
                - {"type": "tool_end", "tool_name": str, "agent": str}
                - {"type": "delta", "text": str, "agent": str} - LLM text chunks
                - {"type": "result", "data": Dict, "agent": str}
                - {"type": "error", "error": str, "agent": str}
        """
        try:
            task_type = "security_analysis"

            # Yield initial thinking event
            yield {
                "type": "thinking",
                "agent": "SecurityCoordinator",
                "thought": "Analyzing security question and determining workflow",
                "roadmap": [
                    {
                        "step": "1",
                        "description": "Route to appropriate security agent"
                    },
                    {
                        "step": "2",
                        "description": "Execute security analysis with LLM"
                    },
                    {
                        "step": "3",
                        "description": "Stream response to user"
                    }
                ]
            }

            # Create agent
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

            # Prepare task
            task = {
                "action": "analyze_vulnerabilities",
                "question": question,
                "target": None,
                "vulnerability_data": {}
            }

            # Stream agent execution
            async for event in agent.execute_task_streaming(task):
                yield event

        except Exception as e:
            logger.error(f"Error in streaming coordination: {e}", exc_info=True)

            yield {
                "type": "error",
                "error_type": "StreamingCoordinationError",
                "error_message": str(e),
                "agent": "SecurityCoordinator"
            }
