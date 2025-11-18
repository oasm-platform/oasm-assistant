from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional
import uuid

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
    Simplified Base Agent Interface

    Provides minimal structure for all agents without heavy dependencies.
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

        logger.info(f"Initialized agent: {self.name} ({self.role.value})")

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
                logger.error(f"LangGraph node execution failed for {self.name}: {e}")
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
        """Execute agent task"""
        pass
