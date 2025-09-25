from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Any, Optional, TypedDict
import uuid

from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.language_models import BaseLanguageModel

from common.logger import logger
from llms import llm_manager
from llms.prompts import SecurityAgentPrompts
from .environment import AgentEnvironment
from .memory import AgentMemory
from .perception import PerceptionSystem
from .state import AgentState


class AgentType(Enum):
    REFLEX = "reflex"
    GOAL_BASED = "goal_based"
    UTILITY_BASED = "utility_based"
    LEARNING = "learning"


class AgentRole(Enum):
    THREAT_INTELLIGENCE_AGENT = "threat_intelligence_agent"
    ANALYSIS_AGENT = "analysis_agent"
    INCIDENT_RESPONSE_AGENT = "incident_response_agent"
    ORCHESTRATION_AGENT = "orchestration_agent"


@dataclass
class AgentCapability:
    name: str
    description: str
    tools: List[str] = field(default_factory=list)
    confidence: float = 1.0
    enabled: bool = True


class AgentState(TypedDict):
    messages: List[Any]
    current_task: Optional[Dict[str, Any]]
    agent_results: Dict[str, Any]
    next_action: Optional[str]
    error: Optional[str]


class BaseAgent(ABC):
    def __init__(
        self,
        name: str,
        role: AgentRole,
        agent_type: AgentType = AgentType.GOAL_BASED,
        capabilities: List[AgentCapability] = None,
        environment: Optional[AgentEnvironment] = None,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
        **kwargs
    ):
        self.id = str(uuid.uuid4())
        self.name = name
        self.role = role
        self.agent_type = agent_type
        self.capabilities = capabilities or []

        self.environment = environment or AgentEnvironment()
        self.perception = PerceptionSystem(self)
        self.memory = AgentMemory(self.id)
        self.state = AgentState()

        self.current_task: Optional[Dict[str, Any]] = None
        self.execution_count = 0
        self.success_count = 0
        self.failure_count = 0

        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.llm: Optional[BaseLanguageModel] = None
        self.tools = []

        self._initialize_llm()
        self.tools = self.setup_tools()
        self.prompt_template = self._create_security_prompt_template()

        self.max_iterations = kwargs.get('max_iterations', 10)
        self.timeout = kwargs.get('timeout', 300)
        self.debug_mode = kwargs.get('debug_mode', False)

        logger.info(f"Initialized agent: {self.name} ({self.role.value}) with LLM: {self.llm_provider}")

    def to_langgraph_node(self, input_key: str = "task", output_key: str = "result"):
        def node_function(state: Dict[str, Any]) -> Dict[str, Any]:
            try:
                task = state.get(input_key, {})
                result = self.execute_task(task)
                state[output_key] = result

                if "agent_results" not in state:
                    state["agent_results"] = {}
                state["agent_results"][self.name] = result

                return state
            except Exception as e:
                logger.error(f"LangGraph node execution failed for {self.name}: {e}")
                error_result = {"success": False, "error": str(e), "agent": self.name}

                state[output_key] = error_result
                if "agent_results" not in state:
                    state["agent_results"] = {}
                state["agent_results"][self.name] = error_result

                return state

        return node_function

    def _initialize_llm(self):
        try:
            available_providers = llm_manager.get_available_providers()
            if not available_providers:
                logger.warning("No LLM providers available")
                return

            provider = self.llm_provider
            if not provider or provider not in available_providers:
                provider = available_providers[0]

            llm_kwargs = {
                "provider": provider,
                "temperature": 0.1,
                "max_tokens": 4000
            }

            if self.llm_model:
                llm_kwargs["model"] = self.llm_model

            self.llm = llm_manager.get_llm(**llm_kwargs)
            self.llm_provider = provider
            logger.info(f"LLM initialized: {provider}")

        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            self.llm = None

    def _create_security_prompt_template(self) -> ChatPromptTemplate:
        capabilities = [cap.name for cap in self.capabilities]
        system_prompt = SecurityAgentPrompts.get_base_security_prompt(
            self.name,
            self.role.value,
            capabilities
        )

        return ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])

    def query_llm(self, message: str, context: Dict[str, Any] = None) -> str:
        if not self.llm:
            logger.error("LLM not initialized")
            return "LLM not available"

        try:
            security_context = ""
            if context:
                security_context = f"""
Current Security Context:
- Alert Level: {context.get('alert_level', 'unknown')}
- Active Threats: {context.get('active_threats', [])}
- Recent Events: {context.get('recent_events', [])}
- Environment State: {context.get('environment_state', {})}
"""

            formatted_message = f"{security_context}\n\nQuery: {message}"
            messages = [HumanMessage(content=formatted_message)]
            response = self.llm.invoke(messages)

            if hasattr(response, 'content'):
                return response.content
            else:
                return str(response)

        except Exception as e:
            logger.error(f"LLM query failed: {e}")
            return f"Error querying LLM: {e}"

    def add_capability(self, capability: AgentCapability):
        self.capabilities.append(capability)
        logger.info(f"Added capability '{capability.name}' to agent {self.name}")

    def perceive(self) -> Dict[str, Any]:
        return self.perception.perceive()

    def get_performance_metrics(self) -> Dict[str, Any]:
        total_executions = self.success_count + self.failure_count
        success_rate = self.success_count / total_executions if total_executions > 0 else 0

        return {
            "agent_id": self.id,
            "agent_name": self.name,
            "role": self.role.value,
            "total_executions": total_executions,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": success_rate
        }

    @abstractmethod
    def setup_tools(self) -> List[Any]:
        pass

    @abstractmethod
    def create_prompt_template(self) -> str:
        pass

    @abstractmethod
    def process_observation(self, observation: Any) -> Dict[str, Any]:
        pass

    @abstractmethod
    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        pass