from typing import Dict, Any
from common.logger import logger
from datetime import datetime
from enum import Enum


class ThreatLevel(Enum):
    """Threat levels for OASM environment monitoring"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EnvironmentData:
    """Environment data container for OASM agents"""
    def __init__(self, data: Dict[str, Any] = None):
        self.data = data or {}

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any):
        self.data[key] = value


class AgentEnvironment:
    """Simplified security environment for OASM agents"""

    def __init__(self):
        # Basic environment state
        self.environmental_state: Dict[str, Any] = {
            "timestamp": datetime.now(),
            "threat_level": ThreatLevel.LOW.value,
            "active_threats": [],
            "security_events": []
        }

        logger.info("OASM security environment initialized")

    def get_environment_state(self) -> Dict[str, Any]:
        """Get current security environment state"""
        self.environmental_state.update({
            "timestamp": datetime.now()
        })
        return self.environmental_state.copy()

    def add_threat(self, threat_data: Dict[str, Any]):
        """Add threat to environment"""
        threat_entry = {
            **threat_data,
            "detected_at": datetime.now(),
            "status": "active"
        }
        self.environmental_state["active_threats"].append(threat_entry)
        logger.warning(f"Threat added to environment: {threat_data.get('type', 'unknown')}")

    def add_security_event(self, event_data: Dict[str, Any]):
        """Add security event to environment"""
        event_entry = {
            **event_data,
            "timestamp": datetime.now()
        }
        self.environmental_state["security_events"].append(event_entry)

        # Keep only last 100 events
        if len(self.environmental_state["security_events"]) > 100:
            self.environmental_state["security_events"] = self.environmental_state["security_events"][-100:]

    def update_threat_level(self, new_level: ThreatLevel):
        """Update current threat level"""
        old_level = self.environmental_state["threat_level"]
        self.environmental_state["threat_level"] = new_level.value
        logger.info(f"Threat level updated from {old_level} to {new_level.value}")