from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional, AsyncGenerator
import uuid

from langchain_core.messages import BaseMessage
from common.logger import logger


class AgentType(Enum):
    """Agent type classification"""
    REFLEX = "reflex"
    GOAL_BASED = "goal_based"
    UTILITY_BASED = "utility_based"
    LEARNING = "learning"


class AgentRole(Enum):
    """Agent role definition"""
    THREAT_INTELLIGENCE_AGENT = "threat_intelligence_agent"
    ANALYSIS_AGENT = "analysis_agent"
    INCIDENT_RESPONSE_AGENT = "incident_response_agent"
    ORCHESTRATION_AGENT = "orchestration_agent"
    NUCLEI_GENERATOR_AGENT = "nuclei_generator_agent"


@dataclass
class AgentCapability:
    """Agent capability definition"""
    name: str
    description: str
    tools: List[str] = field(default_factory=list)
    confidence: float = 1.0
    enabled: bool = True


class BaseAgent(ABC):
    """
    Base Agent Interface with streaming support

    Provides structure for all agents with both synchronous and streaming execution modes.
    Agents can override and extend as needed.
    """

    def __init__(
        self,
        name: str,
        role: AgentRole,
        agent_type: AgentType = AgentType.GOAL_BASED,
        capabilities: Optional[List[AgentCapability]] = None,
        **kwargs
    ):
        """
        Initialize base agent

        Args:
            name: Agent name
            role: Agent role from AgentRole enum
            agent_type: Agent type from AgentType enum
            capabilities: List of agent capabilities
            **kwargs: Additional configuration
        """
        # Core identity
        self.id = str(uuid.uuid4())
        self.name = name
        self.role = role
        self.agent_type = agent_type
        self.capabilities = capabilities or []

        # Configuration
        self.max_iterations = kwargs.get('max_iterations', 10)
        self.timeout = kwargs.get('timeout', 300)
        self.debug_mode = kwargs.get('debug_mode', False)

        logger.debug("Initialized agent: {} ({})", self.name, self.role.value)

    def to_langgraph_node(self, input_key: str = "task", output_key: str = "result"):
        """
        Convert agent to LangGraph node function

        Args:
            input_key: Key to read task from state
            output_key: Key to write result to state

        Returns:
            Callable node function for LangGraph
        """
        def node_function(state: Dict[str, Any]) -> Dict[str, Any]:
            try:
                task = state.get(input_key, {})
                result = self.execute_task(task)
                state[output_key] = result

                # Store in agent_results for coordinator
                if "agent_results" not in state:
                    state["agent_results"] = {}
                state["agent_results"][self.name] = result

                return state

            except Exception as e:
                logger.error("LangGraph node execution failed for {}: {}", self.name, e)
                error_result = {
                    "success": False,
                    "error": str(e),
                    "agent": self.name
                }

                state[output_key] = error_result
                if "agent_results" not in state:
                    state["agent_results"] = {}
                state["agent_results"][self.name] = error_result

                return state

        return node_function

    @abstractmethod
    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute agent task (synchronous)

        Args:
            task: Task dictionary with action and parameters

        Returns:
            Result dictionary with success status and data
        """
        pass

    async def execute_task_streaming(self, task: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute agent task with streaming (asynchronous)

        This is the default implementation that falls back to synchronous execution.
        Agents should override this method to provide true streaming support.

        Args:
            task: Task dictionary with action and parameters

        Yields:
            Streaming events:
            - {"type": "thinking", "thought": str, "agent": str}
            - {"type": "tool_start", "tool_name": str, "agent": str}
            - {"type": "tool_output", "output": Any, "agent": str}
            - {"type": "delta", "text": str, "agent": str}
            - {"type": "result", "data": Dict, "agent": str}
            - {"type": "error", "error": str, "agent": str}
        """
        try:
            # Yield thinking event
            yield {
                "type": "thinking",
                "thought": "{} is processing the task".format(self.name),
                "agent": self.name
            }

            # Execute synchronously (fallback)
            result = self.execute_task(task)

            # Yield result
            yield {
                "type": "result",
                "data": result,
                "agent": self.name
            }

        except Exception as e:
            logger.error("Streaming task execution failed: {}", e)
            yield {
                "type": "error",
                "error": str(e),
                "agent": self.name
            }

    async def stream_llm_response(
        self,
        llm: Any,
        prompt: Any,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Stream LLM response chunks (like ChatGPT/Claude)

        This is a utility method for agents to stream LLM responses naturally.

        Args:
            llm: LLM instance with astream support
            prompt: Prompt to send to LLM
            **kwargs: Additional LLM parameters

        Yields:
            Text chunks from LLM as they are generated
        """
        try:
            async for chunk in llm.astream(prompt, **kwargs):
                if isinstance(chunk, BaseMessage) and chunk.content:
                    yield chunk.content
                elif isinstance(chunk, str):
                    yield chunk
        except Exception as e:
            logger.error("LLM streaming failed: {}", e)
            raise
