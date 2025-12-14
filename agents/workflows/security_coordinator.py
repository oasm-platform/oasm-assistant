"""Multi-agent security workflow orchestration using LangGraph"""

from typing import Dict, Any, List, Optional, TypedDict, AsyncGenerator, Annotated

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.base import Checkpoint

from common.logger import logger
from common.config import configs
from agents.specialized import AnalysisAgent, OrchestrationAgent
from agents.core.memory import STMCheckpointer
from agents.core.memory import STMCheckpointer


class SecurityWorkflowState(TypedDict):
    """State container for security workflow execution"""
    messages: Annotated[List[Any], add_messages]
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
        
        # Initialize checkpointer
        checkpointer = STMCheckpointer()

        return workflow.compile(checkpointer=checkpointer)

    def execute_security_task(self, task: Dict[str, Any], conversation_id: Optional[str] = None) -> Dict[str, Any]:
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

            config = {"configurable": {"thread_id": conversation_id}} if conversation_id else None
            final_state = self.workflow_graph.invoke(initial_state, config=config)

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
            # STM (Short Term Memory): Use sliding window defined in configs
            chat_history = []
            ltm_context = "" # Placeholder for Long-Term Memory

            if state.get("messages"):
                # Get messages for context window optimization based on config
                # Use stm_context_limit (Standard: 3-5 terms)
                window_size = configs.memory.stm_context_limit
                recent_messages = state["messages"][-window_size:]
                for msg in recent_messages:
                    role = "user" if msg.type == "human" else "assistant"
                    chat_history.append({"role": role, "content": msg.content})

            # Future LTM Logic:
            # if configs.memory.ltm_enabled:
            #     ltm_context = retrieve_long_term_memory(state["question"])

            task = {
                "action": action,
                "vulnerability_data": state["vulnerability_data"],
                "target": state["target"],
                "question": state["question"],
                "chat_history": chat_history # Pass accumulated history
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

    def _get_chat_history_from_memory(self, conversation_id: str) -> List[Dict]:
        """Helper to retrieve and format chat history from STM checkpointer"""
        chat_history = []
        if not conversation_id:
            return chat_history

        try:
            checkpointer = self.workflow_graph.checkpointer
            if not checkpointer:
                return chat_history

            config = {"configurable": {"thread_id": conversation_id}}
            checkpoint_tuple = checkpointer.get_tuple(config)
            
            if checkpoint_tuple and checkpoint_tuple.checkpoint:
                # Get summary from metadata
                metadata = checkpoint_tuple.metadata or {}
                summary = metadata.get('summary', "")
                
                if summary:
                    # Add summary as context at the beginning
                    chat_history.append({
                        "role": "system", 
                        "content": f"Previous conversation summary: {summary}"
                    })
                
                # Get recent messages
                messages = checkpoint_tuple.checkpoint['channel_values'].get('messages', [])
                
                # STM: Sliding window based on config
                # Use stm_context_limit (Standard: 3-5 terms)
                window_size = configs.memory.stm_context_limit
                for msg in messages[-window_size:]:
                    role = "user" if msg.type == "human" else "assistant"
                    chat_history.append({"role": role, "content": msg.content})
                    
        except Exception as e:
            logger.error(f"Failed to retrieve chat history from memory: {e}")
            
        return chat_history

    async def update_memory(self, conversation_id: str, question: str, answer: str):
        """Update memory (Delegate logic to STMCheckpointer)"""
        if not conversation_id:
            return

        try:
            config = {"configurable": {"thread_id": conversation_id}}
            checkpointer = self.workflow_graph.checkpointer
            
            if not checkpointer:
                logger.warning("No checkpointer available")
                return
            
            # Get current checkpoint
            checkpoint_tuple = checkpointer.get_tuple(config)
            
            current_messages = []
            metadata = {}
            
            if checkpoint_tuple and checkpoint_tuple.checkpoint:
                current_checkpoint = checkpoint_tuple.checkpoint
                metadata = checkpoint_tuple.metadata or {}
                current_messages = current_checkpoint.get('channel_values', {}).get('messages', [])
            else:
                 # Create new checkpoint structure if needed
                current_checkpoint = {
                    'v': 1,
                    'id': conversation_id,
                    'ts': None, # Timestamp handled by checkpointer usually
                    'channel_values': {},
                    'channel_versions': {},
                    'versions_seen': {}
                }

            # Append new messages (Let Checkpointer handle truncation/summary)
            new_messages = current_messages + [
                HumanMessage(content=question),
                AIMessage(content=answer)
            ]
            
            # Prepare updated checkpoint
            updated_checkpoint = current_checkpoint.copy()
            if 'channel_values' not in updated_checkpoint:
                updated_checkpoint['channel_values'] = {}
            updated_checkpoint['channel_values']['messages'] = new_messages
            
            # Save using checkpointer (It will handle optimization internally)
            # Use aput if available for async, otherwise put
            if hasattr(checkpointer, 'aput'):
                await checkpointer.aput(
                    config,
                    updated_checkpoint,
                    metadata,
                    {} 
                )
            else:
                 checkpointer.put(
                    config,
                    updated_checkpoint,
                    metadata,
                    {} 
                )
                
        except Exception as e:
            logger.error(f"Failed to update memory: {e}", exc_info=True)

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
        question: str,
        conversation_id: Optional[str] = None
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

            # Chat history is now handled by LangGraph state + conversation_id checkpointer
            # We use the helper method to retrieve formatted history from STM
            chat_history = self._get_chat_history_from_memory(conversation_id) if conversation_id else []
            
            task = {
                "action": "analyze_vulnerabilities",
                "question": question,
                "target": None,
                "vulnerability_data": {},
            }
            
            task["chat_history"] = chat_history

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
