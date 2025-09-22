from typing import Dict, Any, List
from datetime import datetime
from enum import Enum
from common.logger import logger


class AgentStatus(Enum):
    """Agent operational status"""
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    ERROR = "error"


class SecurityAlertLevel(Enum):
    """Security alert levels for agent state"""
    GREEN = "green"     # Normal operations
    YELLOW = "yellow"   # Elevated awareness
    ORANGE = "orange"   # High alert
    RED = "red"         # Critical threat detected


class AgentState:
    """Simplified agent state for OASM security operations"""

    def __init__(self):
        # Basic agent state
        self.status = AgentStatus.IDLE
        self.confidence = 1.0
        self.energy = 1.0
        self.last_update = datetime.now()

        # Security-specific state
        self.security_alert_level = SecurityAlertLevel.GREEN
        self.active_threats: List[str] = []
        self.threats_detected = 0
        self.last_threat_analysis = None

        # Custom state for specific agent implementations
        self.custom_state: Dict[str, Any] = {}

        logger.debug("Agent state initialized")

    def update_status(self, new_status: AgentStatus):
        """Update agent status"""
        old_status = self.status
        self.status = new_status
        self.last_update = datetime.now()
        logger.info(f"Agent status updated from {old_status.value} to {new_status.value}")

    def update_security_alert_level(self, new_level: SecurityAlertLevel):
        """Update security alert level"""
        old_level = self.security_alert_level
        self.security_alert_level = new_level
        self.last_update = datetime.now()
        logger.info(f"Security alert level updated from {old_level.value} to {new_level.value}")

    def add_active_threat(self, threat_id: str):
        """Add active threat"""
        if threat_id not in self.active_threats:
            self.active_threats.append(threat_id)
            self.threats_detected += 1
            self.last_update = datetime.now()
            logger.warning(f"Active threat added: {threat_id}")

    def remove_active_threat(self, threat_id: str):
        """Remove active threat"""
        if threat_id in self.active_threats:
            self.active_threats.remove(threat_id)
            self.last_update = datetime.now()
            logger.info(f"Active threat removed: {threat_id}")

    def adjust_confidence(self, delta: float):
        """Adjust confidence level"""
        self.confidence = max(0.0, min(1.0, self.confidence + delta))
        self.last_update = datetime.now()

    def adjust_energy(self, delta: float):
        """Adjust energy level"""
        self.energy = max(0.0, min(1.0, self.energy + delta))
        self.last_update = datetime.now()

    def update(self, key: str, value: Any):
        """Update custom state"""
        self.custom_state[key] = value
        self.last_update = datetime.now()

    def get(self, key: str, default: Any = None) -> Any:
        """Get custom state value"""
        return self.custom_state.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary"""
        return {
            "status": self.status.value,
            "confidence": self.confidence,
            "energy": self.energy,
            "security_alert_level": self.security_alert_level.value,
            "active_threats": self.active_threats.copy(),
            "threats_detected": self.threats_detected,
            "last_update": self.last_update.isoformat(),
            "custom_state": self.custom_state.copy()
        }