"""
Perception layer for agents in OASM Assistant
"""
from typing import Dict, Any, List, Optional, Callable
from pydantic import BaseModel, Field
import asyncio
from datetime import datetime


class PerceptionInput(BaseModel):
    """Input for perception processing"""
    source: str  # e.g., "environment", "user", "tool", "system"
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)
    priority: int = 1  # 1-10, 10 being highest priority


class PerceptionOutput(BaseModel):
    """Output from perception processing"""
    processed_data: Dict[str, Any]
    significance: float  # 0.0 to 1.0
    actions_suggested: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)


class AgentPerception:
    """Main perception system for agents"""
    
    def __init__(self):
        self.sensors: Dict[str, Callable] = {}
        self.processors: Dict[str, Callable] = {}
        self.last_perceptions: List[PerceptionOutput] = []
    
    def register_sensor(self, name: str, sensor_func: Callable) -> None:
        """Register a new sensor"""
        self.sensors[name] = sensor_func
    
    def register_processor(self, name: str, processor_func: Callable) -> None:
        """Register a new perception processor"""
        self.processors[name] = processor_func
    
    async def perceive(self, input_data: PerceptionInput) -> PerceptionOutput:
        """Process perception input and generate output"""
        # Apply registered processors
        processed_data = input_data.data.copy()
        
        for processor_name, processor_func in self.processors.items():
            try:
                # Each processor can modify the data
                result = await processor_func(processed_data) if asyncio.iscoroutinefunction(processor_func) else processor_func(processed_data)
                if isinstance(result, dict):
                    processed_data.update(result)
            except Exception as e:
                # Log error but continue with other processors
                print(f"Error in processor {processor_name}: {e}")
        
        # Create perception output
        perception_output = PerceptionOutput(
            processed_data=processed_data,
            significance=self._calculate_significance(input_data, processed_data)
        )
        
        # Store recent perceptions
        self.last_perceptions.append(perception_output)
        if len(self.last_perceptions) > 100:  # Limit to 100 recent perceptions
            self.last_perceptions.pop(0)
        
        return perception_output
    
    def _calculate_significance(self, input_data: PerceptionInput, processed_data: Dict[str, Any]) -> float:
        """Calculate the significance of a perception"""
        # Base significance on input priority
        significance = input_data.priority / 10.0
        
        # Increase significance for certain keywords or data types
        data_str = str(processed_data).lower()
        important_keywords = ["error", "critical", "urgent", "important", "alert"]
        
        for keyword in important_keywords:
            if keyword in data_str:
                significance = min(1.0, significance + 0.2)
        
        return significance
    
    async def perceive_from_sensors(self) -> List[PerceptionOutput]:
        """Gather perceptions from all registered sensors"""
        perceptions = []
        
        for sensor_name, sensor_func in self.sensors.items():
            try:
                # Get data from sensor
                sensor_data = await sensor_func() if asyncio.iscoroutinefunction(sensor_func) else sensor_func()
                
                if sensor_data:
                    # Create perception input
                    perception_input = PerceptionInput(
                        source=sensor_name,
                        data=sensor_data,
                        priority=5  # Default priority
                    )
                    
                    # Process perception
                    perception_output = await self.perceive(perception_input)
                    perceptions.append(perception_output)
            except Exception as e:
                # Log error but continue with other sensors
                print(f"Error in sensor {sensor_name}: {e}")
        
        return perceptions
    
    def get_recent_perceptions(self, count: int = 10) -> List[PerceptionOutput]:
        """Get recent perceptions"""
        return self.last_perceptions[-count:] if self.last_perceptions else []
    
    def get_significant_perceptions(self, threshold: float = 0.5) -> List[PerceptionOutput]:
        """Get perceptions above a significance threshold"""
        return [
            p for p in self.last_perceptions 
            if p.significance >= threshold
        ]