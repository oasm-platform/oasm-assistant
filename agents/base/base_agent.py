"""
Abstract base agent class for OASM Assistant
"""
from typing import Dict, Any, List, Callable
from abc import ABC, abstractmethod
from datetime import datetime
import asyncio
import traceback
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .agent_state import AgentState, AgentStatus, AgentGoal
from .agent_memory import AgentMemory
from .agent_perception import AgentPerception, PerceptionInput, PerceptionOutput


class BaseAgent(ABC):
    """Base agent class for OASM Assistant with all core components"""
    
    def __init__(self, agent_id: str, name: str = "BaseAgent"):
        self.agent_id = agent_id
        self.name = name
        
        # Core components
        self.state = AgentState(agent_id=agent_id)
        self.memory = AgentMemory()
        self.perception = AgentPerception()
        
        # Message passing system
        self.message_queue: List[Dict[str, Any]] = []
        self.message_handlers: Dict[str, Callable] = {}
        
        # Tool interface
        self.tools: Dict[str, Callable] = {}
        
        # Error handling
        self.error_count = 0
        self.max_errors = 5
        self.recovery_strategies: List[Callable] = []
        
        # Initialize langgraph workflow
        self.workflow = self._create_workflow()
        self.checkpointer = MemorySaver()
        self.app = self.workflow.compile(checkpointer=self.checkpointer)
    
    # === Agent State Management ===
    
    def update_status(self, status: AgentStatus) -> None:
        """Update agent status"""
        self.state.update_status(status)
    
    def add_goal(self, goal: AgentGoal) -> None:
        """Add a new goal to the agent"""
        self.state.add_goal(goal)
    
    def update_goal_status(self, goal_id: str, status: str) -> bool:
        """Update goal status"""
        return self.state.update_goal_status(goal_id, status)
    
    # === Message Passing System ===
    
    def register_message_handler(self, message_type: str, handler: Callable) -> None:
        """Register a message handler for a specific message type"""
        self.message_handlers[message_type] = handler
    
    def send_message(self, recipient_id: str, message_type: str, content: Dict[str, Any]) -> None:
        """Send a message to another agent or system component"""
        message = {
            "sender_id": self.agent_id,
            "recipient_id": recipient_id,
            "message_type": message_type,
            "content": content,
            "timestamp": datetime.now()
        }
        self.message_queue.append(message)
    
    async def process_messages(self) -> None:
        """Process all messages in the queue"""
        while self.message_queue:
            message = self.message_queue.pop(0)
            try:
                await self._handle_message(message)
            except Exception as e:
                await self._handle_error(e, {"context": "message_processing", "message": message})
    
    async def _handle_message(self, message: Dict[str, Any]) -> None:
        """Handle a single message"""
        message_type = message.get("message_type")
        if message_type in self.message_handlers:
            handler = self.message_handlers[message_type]
            if asyncio.iscoroutinefunction(handler):
                await handler(message)
            else:
                handler(message)
        else:
            # Default message handling
            await self._default_message_handler(message)
    
    async def _default_message_handler(self, message: Dict[str, Any]) -> None:
        """Default message handler"""
        print(f"[{self.name}] Received message: {message['message_type']} from {message['sender_id']}")
        # Add to context history
        self.state.add_to_context_history({
            "role": "system_message",
            "content": f"Received {message['message_type']} from {message['sender_id']}",
            "timestamp": message["timestamp"]
        })
    
    # === Tool Interface ===
    
    def register_tool(self, name: str, tool_func: Callable) -> None:
        """Register a tool that the agent can use"""
        self.tools[name] = tool_func
        self.state.tools.append(name)
    
    async def use_tool(self, tool_name: str, **kwargs) -> Any:
        """Use a registered tool"""
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not registered")
        
        tool_func = self.tools[tool_name]
        try:
            if asyncio.iscoroutinefunction(tool_func):
                return await tool_func(**kwargs)
            else:
                return tool_func(**kwargs)
        except Exception as e:
            await self._handle_error(e, {"context": "tool_usage", "tool": tool_name})
            raise
    
    # === Perception Layer ===
    
    async def perceive(self, input_data: PerceptionInput) -> PerceptionOutput:
        """Process perception input"""
        return await self.perception.perceive(input_data)
    
    async def perceive_from_sensors(self) -> List[PerceptionOutput]:
        """Gather perceptions from all sensors"""
        return await self.perception.perceive_from_sensors()
    
    # === Basic Reasoning Loop ===
    
    @abstractmethod
    async def plan(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Abstract method for planning - must be implemented by subclasses"""
        pass
    
    @abstractmethod
    async def execute(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Abstract method for execution - must be implemented by subclasses"""
        pass
    
    async def reason(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Basic reasoning loop"""
        try:
            self.update_status(AgentStatus.THINKING)
            
            # 1. Perceive
            perception_input = PerceptionInput(
                source="reasoning_loop",
                data=input_data
            )
            perception = await self.perceive(perception_input)
            
            # 2. Plan
            plan = await self.plan(perception.processed_data)
            
            # 3. Execute
            result = await self.execute(plan)
            
            # 4. Update memory
            self.memory.add_memory(
                content={
                    "input": input_data,
                    "perception": perception.processed_data,
                    "plan": plan,
                    "result": result
                },
                importance=perception.significance,
                tags=["reasoning_cycle"]
            )
            
            self.update_status(AgentStatus.IDLE)
            return result
            
        except Exception as e:
            await self._handle_error(e, {"context": "reasoning_loop"})
            raise
    
    # === LangGraph Workflow ===
    
    def _create_workflow(self) -> StateGraph:
        """Create the agent workflow using LangGraph"""
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("perceive", self._workflow_perceive)
        workflow.add_node("plan", self._workflow_plan)
        workflow.add_node("execute", self._workflow_execute)
        workflow.add_node("reflect", self._workflow_reflect)
        
        # Add edges
        workflow.add_edge("perceive", "plan")
        workflow.add_edge("plan", "execute")
        workflow.add_edge("execute", "reflect")
        workflow.add_edge("reflect", END)
        
        # Set entry point
        workflow.set_entry_point("perceive")
        
        return workflow
    
    async def _workflow_perceive(self, state: AgentState) -> Dict[str, Any]:
        """Workflow node for perception"""
        # In a real implementation, this would gather information from environment
        return {"status": AgentStatus.THINKING}
    
    async def _workflow_plan(self, state: AgentState) -> Dict[str, Any]:
        """Workflow node for planning"""
        # In a real implementation, this would create a plan
        return {"status": AgentStatus.THINKING}
    
    async def _workflow_execute(self, state: AgentState) -> Dict[str, Any]:
        """Workflow node for execution"""
        # In a real implementation, this would execute actions
        return {"status": AgentStatus.THINKING}
    
    async def _workflow_reflect(self, state: AgentState) -> Dict[str, Any]:
        """Workflow node for reflection"""
        # In a real implementation, this would evaluate results
        return {"status": AgentStatus.IDLE}
    
    async def run_workflow(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run the agent workflow"""
        try:
            self.update_status(AgentStatus.THINKING)
            config = {"configurable": {"thread_id": self.agent_id}}
            result = await self.app.ainvoke(input_data, config=config)
            self.update_status(AgentStatus.IDLE)
            return result
        except Exception as e:
            await self._handle_error(e, {"context": "workflow_execution"})
            raise
    
    # === Error Handling and Recovery ===
    
    def add_recovery_strategy(self, strategy: Callable) -> None:
        """Add a recovery strategy for error handling"""
        self.recovery_strategies.append(strategy)
    
    async def _handle_error(self, error: Exception, context: Dict[str, Any]) -> None:
        """Handle errors and attempt recovery"""
        self.error_count += 1
        self.update_status(AgentStatus.ERROR)
        
        error_info = {
            "error": str(error),
            "type": type(error).__name__,
            "traceback": traceback.format_exc(),
            "context": context,
            "timestamp": datetime.now()
        }
        
        print(f"[{self.name}] Error occurred: {error_info}")
        
        # Add to memory
        self.memory.add_memory(
            content=error_info,
            importance=0.9,  # High importance
            tags=["error"],
            is_long_term=True
        )
        
        # Add to context history
        self.state.add_to_context_history({
            "role": "system_error",
            "content": str(error),
            "timestamp": error_info["timestamp"]
        })
        
        # Attempt recovery if we haven't exceeded max errors
        if self.error_count <= self.max_errors:
            await self._attempt_recovery(error_info)
        else:
            print(f"[{self.name}] Max errors exceeded. Agent may be in unstable state.")
    
    async def _attempt_recovery(self, error_info: Dict[str, Any]) -> None:
        """Attempt to recover from an error"""
        print(f"[{self.name}] Attempting recovery...")
        
        # Try registered recovery strategies
        for strategy in self.recovery_strategies:
            try:
                if asyncio.iscoroutinefunction(strategy):
                    await strategy(error_info)
                else:
                    strategy(error_info)
                print(f"[{self.name}] Recovery strategy succeeded")
                self.update_status(AgentStatus.IDLE)
                return
            except Exception as recovery_error:
                print(f"[{self.name}] Recovery strategy failed: {recovery_error}")
        
        # Default recovery: reset to idle state
        print(f"[{self.name}] Using default recovery - resetting to idle")
        self.update_status(AgentStatus.IDLE)
    
    def reset_error_count(self) -> None:
        """Reset the error count"""
        self.error_count = 0
    
    # === Utility Methods ===
    
    async def run(self) -> None:
        """Main run loop for the agent"""
        print(f"[{self.name}] Agent started")
        self.update_status(AgentStatus.IDLE)
        
        try:
            # Main agent loop
            while self.state.status != AgentStatus.FINISHED:
                # Process messages
                await self.process_messages()
                
                # Check for goals to work on
                pending_goals = [g for g in self.state.goals if g.status == "pending"]
                if pending_goals:
                    # Work on the highest priority goal
                    pending_goals.sort(key=lambda g: g.priority, reverse=True)
                    goal = pending_goals[0]
                    self.update_goal_status(goal.id, "in_progress")
                    
                    # This is a simplified implementation
                    # In a real agent, this would involve more complex planning
                    print(f"[{self.name}] Working on goal: {goal.description}")
                    self.update_goal_status(goal.id, "completed")
                
                # Small delay to prevent busy waiting
                await asyncio.sleep(0.1)
                
        except Exception as e:
            await self._handle_error(e, {"context": "main_loop"})
        finally:
            print(f"[{self.name}] Agent stopped")