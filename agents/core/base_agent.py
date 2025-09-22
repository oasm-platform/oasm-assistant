from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
import uuid
import logging
from enum import Enum

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.language_models import BaseLanguageModel
from langchain.memory import ConversationBufferWindowMemory

# Try to import AgentExecutor, fallback if not available
try:
    from langchain.agents import AgentExecutor
except ImportError:
    AgentExecutor = None

# Import LLM manager
from llms import llm_manager

from .environment import AgentEnvironment
from .perception import PerceptionSystem
from .memory import AgentMemory
from .state import AgentState

logger = logging.getLogger("agents")


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


@dataclass
class AgentGoal:
    """Agent goal for threat monitoring and security tasks"""
    id: str
    description: str
    priority: int
    status: str = "pending"  # pending, active, completed, failed
    created_at: datetime = field(default_factory=datetime.utcnow)
    deadline: Optional[datetime] = None
    success_criteria: List[str] = field(default_factory=list)


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

        # Goals and tasks for security operations
        self.goals: List[AgentGoal] = []
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
        self.agent_executor: Optional[AgentExecutor] = None
        self.conversation_memory = ConversationBufferWindowMemory(
            k=kwargs.get('memory_window', 10),
            return_messages=True
        )

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
            self.llm = llm_manager.get_llm(
                provider=provider,
                model=self.llm_model,
                temperature=0.1,  # Lower temperature for security tasks
                max_tokens=4000
            )

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

    async def query_llm(self, message: str, context: Dict[str, Any] = None) -> str:
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

            # Get response
            response = await self.llm.ainvoke(messages)

            # Extract text content
            if hasattr(response, 'content'):
                return response.content
            else:
                return str(response)

        except Exception as e:
            logger.error(f"LLM query failed: {e}")
            return f"Error querying LLM: {e}"

    async def analyze_with_llm(self, data: Dict[str, Any], analysis_type: str = "security") -> Dict[str, Any]:
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

            response = await self.query_llm(
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
                "timestamp": datetime.utcnow(),
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
    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute security task (threat analysis, vulnerability scan, etc.)"""
        pass

    def add_capability(self, capability: AgentCapability):
        """Add security capability to agent"""
        self.capabilities.append(capability)
        logger.info(f"Added capability '{capability.name}' to agent {self.name}")

    def add_goal(self, goal: AgentGoal):
        """Add security goal to agent"""
        self.goals.append(goal)
        self.state.update("goals_count", len(self.goals))
        logger.info(f"Added goal '{goal.description}' to agent {self.name}")

    def perceive(self) -> Dict[str, Any]:
        """Perceive threats and security events in environment"""
        return self.perception.perceive()

    def reason(self, observations: Dict[str, Any]) -> Dict[str, Any]:
        """Reason about security observations using CoT (Chain of Thought)"""
        reasoning_result = {
            "observations_processed": len(observations),
            "timestamp": datetime.utcnow(),
            "confidence": 1.0,
            "threat_indicators": self._extract_threat_indicators(observations),
            "security_context": self._analyze_security_context(observations)
        }

        # Update memory with security observations
        self.memory.add_observation(observations)

        return reasoning_result

    def plan(self, goal: AgentGoal) -> List[Dict[str, Any]]:
        """Plan security actions to achieve goal"""
        plan = []

        # Security-focused planning logic
        if "threat" in goal.description.lower():
            plan.extend(self._plan_threat_analysis(goal))
        elif "vulnerability" in goal.description.lower():
            plan.extend(self._plan_vulnerability_assessment(goal))
        elif "scan" in goal.description.lower():
            plan.extend(self._plan_security_scan(goal))
        else:
            # Generic security analysis
            plan.append({
                "action": "analyze_security_goal",
                "goal_id": goal.id,
                "description": f"Analyze security goal: {goal.description}",
                "priority": goal.priority
            })

        return plan

    async def act(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute security action using ReAct pattern"""
        try:
            action_type = action.get("action")

            # Security-specific actions
            if action_type == "analyze_security_goal":
                return await self._analyze_security_goal(action)
            elif action_type == "run_security_scan":
                return await self._run_security_scan(action)
            elif action_type == "analyze_threat":
                return await self._analyze_threat(action)
            else:
                return await self.execute_task(action)

        except Exception as e:
            logger.error(f"Action execution failed for agent {self.name}: {e}")
            return {"success": False, "error": str(e)}

    async def _analyze_security_goal(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze security goal with threat intelligence"""
        goal_id = action.get("goal_id")
        goal = next((g for g in self.goals if g.id == goal_id), None)

        if not goal:
            return {"success": False, "error": "Goal not found"}

        analysis = {
            "goal_id": goal_id,
            "security_feasibility": self._assess_security_feasibility(goal),
            "required_tools": self._get_required_security_tools(goal),
            "threat_level": self._assess_threat_level_for_goal(goal),
            "estimated_time": self._estimate_completion_time(goal),
            "success": True
        }

        return analysis

    async def _run_security_scan(self, action: Dict[str, Any]) -> Dict[str, Any]:
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

    async def _analyze_threat(self, action: Dict[str, Any]) -> Dict[str, Any]:
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

    def _plan_threat_analysis(self, goal: AgentGoal) -> List[Dict[str, Any]]:
        """Plan threat analysis actions"""
        return [
            {
                "action": "gather_threat_intelligence",
                "goal_id": goal.id,
                "description": "Gather threat intelligence data",
                "priority": goal.priority
            },
            {
                "action": "analyze_threat",
                "goal_id": goal.id,
                "description": "Analyze threat indicators",
                "priority": goal.priority
            }
        ]

    def _plan_vulnerability_assessment(self, goal: AgentGoal) -> List[Dict[str, Any]]:
        """Plan vulnerability assessment actions"""
        return [
            {
                "action": "run_security_scan",
                "scan_type": "vulnerability",
                "goal_id": goal.id,
                "description": "Run vulnerability scan",
                "priority": goal.priority
            },
            {
                "action": "analyze_vulnerabilities",
                "goal_id": goal.id,
                "description": "Analyze discovered vulnerabilities",
                "priority": goal.priority
            }
        ]

    def _plan_security_scan(self, goal: AgentGoal) -> List[Dict[str, Any]]:
        """Plan security scan actions"""
        return [
            {
                "action": "run_security_scan",
                "scan_type": "comprehensive",
                "goal_id": goal.id,
                "description": "Run comprehensive security scan",
                "priority": goal.priority
            }
        ]

    def _assess_security_feasibility(self, goal: AgentGoal) -> float:
        """Assess security goal feasibility"""
        # Consider available security tools and capabilities
        relevant_caps = [cap for cap in self.capabilities if cap.enabled]
        return min(0.9, len(relevant_caps) * 0.2)

    def _get_required_security_tools(self, goal: AgentGoal) -> List[str]:
        """Get required security tools for goal"""
        tools = []
        goal_desc = goal.description.lower()

        if "scan" in goal_desc:
            tools.extend(["nmap", "nuclei", "httpx"])
        if "vulnerability" in goal_desc:
            tools.extend(["nuclei", "subfinder"])
        if "threat" in goal_desc:
            tools.extend(["threat_intelligence", "ioc_analyzer"])

        return tools

    def _assess_threat_level_for_goal(self, goal: AgentGoal) -> str:
        """Assess threat level for specific goal"""
        threat_keywords = ["critical", "high", "urgent", "immediate"]
        goal_desc = goal.description.lower()

        if any(keyword in goal_desc for keyword in threat_keywords):
            return "high"
        elif goal.priority > 8:
            return "medium"
        else:
            return "low"

    def _assess_goal_feasibility(self, goal: AgentGoal) -> float:
        """Assess general goal feasibility"""
        return self._assess_security_feasibility(goal)

    def _get_required_capabilities(self, goal: AgentGoal) -> List[str]:
        """Get required capabilities for goal"""
        return [cap.name for cap in self.capabilities if cap.enabled]

    def _estimate_completion_time(self, goal: AgentGoal) -> int:
        """Estimate completion time for security goal (seconds)"""
        base_time = 300  # 5 minutes base

        # Adjust based on goal complexity
        if "comprehensive" in goal.description.lower():
            base_time *= 3
        elif "quick" in goal.description.lower():
            base_time //= 2

        return base_time

    def learn_from_experience(self, experience: Dict[str, Any]):
        """Learn from security operation experience"""
        self.memory.add_experience(experience)

        # Update performance metrics
        if experience.get("success"):
            self.success_count += 1
        else:
            self.failure_count += 1

        # Update agent state based on experience
        if experience.get("threat_detected"):
            self.state.adjust_confidence(0.1)
        if experience.get("scan_completed"):
            self.state.adjust_energy(-0.1)

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get security agent performance metrics"""
        total_executions = self.success_count + self.failure_count
        success_rate = self.success_count / total_executions if total_executions > 0 else 0

        return {
            "agent_id": self.id,
            "agent_name": self.name,
            "role": self.role.value,
            "total_executions": total_executions,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": success_rate,
            "goals_count": len(self.goals),
            "active_goals": len([g for g in self.goals if g.status == "active"]),
            "capabilities_count": len(self.capabilities),
            "threat_indicators_processed": self.state.threats_detected,
            "scans_completed": self.state.custom_state.get("completed_scans", 0)
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize OASM agent to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role.value,
            "agent_type": self.agent_type.value,
            "capabilities": [cap.__dict__ for cap in self.capabilities],
            "goals": [goal.__dict__ for goal in self.goals],
            "state": self.state.to_dict(),
            "performance": self.get_performance_metrics(),
            "security_context": {
                "active_threats": len(self._extract_threat_indicators({})),
                "last_scan": self.state.get("last_scan_time"),
                "threat_level": self.state.get("current_threat_level", "low")
            }
        }