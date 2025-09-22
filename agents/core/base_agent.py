from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import uuid
from enum import Enum

from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.language_models import BaseLanguageModel

from llms import llm_manager

from .environment import AgentEnvironment
from .perception import PerceptionSystem
from .memory import AgentMemory
from .state import AgentState

from common.logger import logger


class AgentType(Enum):
    """Types of agents based on AI agent architectures"""
    REFLEX = "reflex"
    GOAL_BASED = "goal_based"
    UTILITY_BASED = "utility_based"
    LEARNING = "learning"


class AgentRole(Enum):
    """Specialized roles for OASM security agents"""
    THREAT_ANALYST = "threat_analyst"
    SECURITY_RESEARCHER = "security_researcher"
    SCAN_ANALYZER = "scan_analyzer"
    VULNERABILITY_ASSESSOR = "vulnerability_assessor"
    INCIDENT_RESPONDER = "incident_responder"
    ORCHESTRATOR = "orchestrator"


@dataclass
class AgentCapability:
    """Agent capability definition with security tools"""
    name: str
    description: str
    tools: List[str] = field(default_factory=list)
    confidence: float = 1.0
    enabled: bool = True




class BaseAgent(ABC):
    """Base class for all OASM security AI agents with LangChain integration"""

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

        # Core components for OASM
        self.environment = environment or AgentEnvironment()
        self.perception = PerceptionSystem(self)
        self.memory = AgentMemory(self.id)
        self.state = AgentState()

        # Current task for security operations
        self.current_task: Optional[Dict[str, Any]] = None

        # Performance tracking for security operations
        self.execution_count = 0
        self.success_count = 0
        self.failure_count = 0

        # LangChain components with LLM manager integration
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.llm: Optional[BaseLanguageModel] = None
        self.tools = []  # Security tools (nuclei, nmap, etc.)
        # Removed unused LangChain components

        # Initialize LLM
        self._initialize_llm()

        # Initialize tools
        self.tools = self.setup_tools()

        # Create prompt template
        self.prompt_template = self._create_security_prompt_template()

        # Configuration
        self.max_iterations = kwargs.get('max_iterations', 10)
        self.timeout = kwargs.get('timeout', 300)
        self.debug_mode = kwargs.get('debug_mode', False)

        logger.info(f"Initialized OASM agent: {self.name} ({self.role.value}) with LLM: {self.llm_provider}")

    @abstractmethod
    def setup_tools(self) -> List[Any]:
        """Setup security tools (nuclei, nmap, subfinder, httpx, etc.) for the agent"""
        pass

    @abstractmethod
    def create_prompt_template(self) -> str:
        """Create LangChain prompt template for security-focused tasks"""
        pass

    def _initialize_llm(self):
        """Initialize LLM using the LLM manager"""
        try:
            # Get available providers
            available_providers = llm_manager.get_available_providers()

            if not available_providers:
                logger.warning("No LLM providers available")
                return

            # Use specified provider or default
            provider = self.llm_provider
            if not provider or provider not in available_providers:
                provider = available_providers[0]  # Use first available
                logger.info(f"Using default LLM provider: {provider}")

            # Initialize LLM
            llm_kwargs = {
                "provider": provider,
                "temperature": 0.1,  # Lower temperature for security tasks
                "max_tokens": 4000
            }

            # Only add model parameter if specified
            if self.llm_model:
                llm_kwargs["model"] = self.llm_model

            self.llm = llm_manager.get_llm(**llm_kwargs)

            self.llm_provider = provider
            logger.info(f"LLM initialized: {provider}")

        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            self.llm = None

    def _create_security_prompt_template(self) -> ChatPromptTemplate:
        """Create security-focused prompt template"""
        system_prompt = f"""You are {self.name}, a specialized AI security agent with the role of {self.role.value}.

Your primary responsibilities:
- Threat detection and analysis
- Vulnerability assessment
- Security monitoring and incident response
- Threat intelligence correlation
- Security tool coordination

Current capabilities: {[cap.name for cap in self.capabilities]}

Always respond with:
1. Clear, actionable security recommendations
2. Risk assessments with severity levels
3. Specific technical details when analyzing threats
4. Confidence levels for your assessments

You have access to security tools and databases. Use your expertise to provide comprehensive security analysis."""

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])

        return prompt

    def query_llm(self, message: str, context: Dict[str, Any] = None) -> str:
        """Query the LLM with security context"""
        if not self.llm:
            logger.error("LLM not initialized")
            return "LLM not available"

        try:
            # Prepare context
            security_context = ""
            if context:
                security_context = f"""
Current Security Context:
- Alert Level: {context.get('alert_level', 'unknown')}
- Active Threats: {context.get('active_threats', [])}
- Recent Events: {context.get('recent_events', [])}
- Environment State: {context.get('environment_state', {})}
"""

            # Format the message with context
            formatted_message = f"{security_context}\n\nQuery: {message}"

            # Create messages
            messages = [
                HumanMessage(content=formatted_message)
            ]

            # Get response - use sync invoke to avoid event loop issues
            response = self.llm.invoke(messages)

            # Extract text content
            if hasattr(response, 'content'):
                return response.content
            else:
                return str(response)

        except Exception as e:
            logger.error(f"LLM query failed: {e}")
            return f"Error querying LLM: {e}"

    def analyze_with_llm(self, data: Dict[str, Any], analysis_type: str = "security") -> Dict[str, Any]:
        """Analyze data using LLM with structured response"""
        if not self.llm:
            return {"error": "LLM not available"}

        try:
            # Prepare analysis prompt
            analysis_prompt = f"""
Analyze the following {analysis_type} data and provide a structured assessment:

Data: {data}

Please provide:
1. Risk Level: (low/medium/high/critical)
2. Key Findings: (bullet points)
3. Threat Indicators: (specific indicators found)
4. Recommendations: (actionable steps)
5. Confidence: (0.0-1.0)

Format your response as structured analysis.
"""

            response = self.query_llm(
                analysis_prompt,
                context={
                    "alert_level": self.state.security_alert_level.value,
                    "active_threats": self.state.active_threats,
                    "environment_state": self.environment.get_environment_state()
                }
            )

            # Parse response (simplified - in production, use structured output)
            return {
                "analysis_type": analysis_type,
                "response": response,
                "timestamp": datetime.now(),
                "agent_id": self.id,
                "confidence": 0.8  # Default confidence
            }

        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return {"error": str(e)}

    @abstractmethod
    def process_observation(self, observation: Any) -> Dict[str, Any]:
        """Process security-related observations from environment"""
        pass

    @abstractmethod
    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute security task (threat analysis, vulnerability scan, etc.)"""
        pass

    def add_capability(self, capability: AgentCapability):
        """Add security capability to agent"""
        self.capabilities.append(capability)
        logger.info(f"Added capability '{capability.name}' to agent {self.name}")


    def perceive(self) -> Dict[str, Any]:
        """Perceive threats and security events in environment"""
        return self.perception.perceive()

    def reason(self, observations: Dict[str, Any]) -> Dict[str, Any]:
        """Reason about security observations using CoT (Chain of Thought)"""
        reasoning_result = {
            "observations_processed": len(observations),
            "timestamp": datetime.now(),
            "confidence": 1.0,
            "threat_indicators": self._extract_threat_indicators(observations),
            "security_context": self._analyze_security_context(observations)
        }

        # Update memory with security observations
        self.memory.add_observation(observations)

        return reasoning_result


    def act(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute security action using ReAct pattern"""
        try:
            action_type = action.get("action")

            # Security-specific actions
            if action_type == "run_security_scan":
                return self._run_security_scan(action)
            elif action_type == "analyze_threat":
                return self._analyze_threat(action)
            else:
                return self.execute_task(action)

        except Exception as e:
            logger.error(f"Action execution failed for agent {self.name}: {e}")
            return {"success": False, "error": str(e)}


    def _run_security_scan(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Run security scan using available tools"""
        scan_type = action.get("scan_type", "basic")
        target = action.get("target")

        if not target:
            return {"success": False, "error": "No target specified for scan"}

        # This would be implemented by specific agent types
        return {
            "success": True,
            "scan_type": scan_type,
            "target": target,
            "results": "Scan completed - implement in subclass"
        }

    def _analyze_threat(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze threat using threat intelligence"""
        threat_data = action.get("threat_data")

        if not threat_data:
            return {"success": False, "error": "No threat data provided"}

        # Threat analysis logic - implement in subclasses
        return {
            "success": True,
            "threat_analysis": "Threat analyzed - implement in subclass",
            "risk_level": "medium",
            "recommendations": []
        }

    def _extract_threat_indicators(self, observations: Dict[str, Any]) -> List[str]:
        """Extract threat indicators from observations"""
        indicators = []

        # Look for security-related keywords
        obs_str = str(observations).lower()
        threat_keywords = ["malware", "attack", "breach", "vulnerability", "exploit",
                          "suspicious", "anomaly", "intrusion", "unauthorized"]

        for keyword in threat_keywords:
            if keyword in obs_str:
                indicators.append(keyword)

        return indicators

    def _analyze_security_context(self, observations: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze security context from observations"""
        return {
            "security_level": "normal",
            "active_threats": len(self._extract_threat_indicators(observations)),
            "requires_attention": False
        }

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get basic security agent performance metrics"""
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