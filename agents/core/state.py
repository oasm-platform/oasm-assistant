from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger("agents")


class AgentStatus(Enum):
    """Agent operational status for OASM security operations"""
    IDLE = "idle"
    THINKING = "thinking"
    PLANNING = "planning"
    EXECUTING = "executing"
    COMMUNICATING = "communicating"
    LEARNING = "learning"
    ERROR = "error"
    # Security-specific statuses
    SCANNING = "scanning"
    ANALYZING_THREATS = "analyzing_threats"
    RESPONDING_TO_INCIDENT = "responding_to_incident"
    MONITORING = "monitoring"
    CORRELATING_INTELLIGENCE = "correlating_intelligence"


class AgentMood(Enum):
    """Agent mood states for security operations"""
    CONFIDENT = "confident"
    UNCERTAIN = "uncertain"
    FOCUSED = "focused"
    OVERWHELMED = "overwhelmed"
    CURIOUS = "curious"
    # Security-specific moods
    VIGILANT = "vigilant"
    CONCERNED = "concerned"
    ALERT = "alert"


class SecurityAlertLevel(Enum):
    """Security alert levels for agent state"""
    GREEN = "green"     # Normal operations
    YELLOW = "yellow"   # Elevated awareness
    ORANGE = "orange"   # High alert
    RED = "red"         # Critical threat detected

class AgentState:
    """Enhanced agent state for OASM security operations"""

    def __init__(self):
        # Basic agent state
        self.status = AgentStatus.IDLE
        self.mood = AgentMood.CONFIDENT
        self.energy_level = 1.0  # 0.0 - 1.0
        self.confidence_level = 0.8  # 0.0 - 1.0
        self.focus_level = 0.8  # 0.0 - 1.0

        # Cognitive load
        self.cognitive_load = 0.0  # 0.0 - 1.0
        self.stress_level = 0.0  # 0.0 - 1.0

        # Current context
        self.current_goal_id: Optional[str] = None
        self.current_task: Optional[Dict[str, Any]] = None
        self.context_stack: List[Dict[str, Any]] = []

        # Performance state
        self.recent_success_rate = 0.0
        self.learning_rate = 0.1

        # Timestamps
        self.last_updated = datetime.utcnow()
        self.last_action = datetime.utcnow()

        # Security-specific state components
        self.security_alert_level = SecurityAlertLevel.GREEN
        self.threat_awareness_level = 0.0  # 0.0 - 1.0
        self.scan_activity_level = 0.0  # 0.0 - 1.0

        # Current security context
        self.active_threats: List[str] = []
        self.current_incident_id: Optional[str] = None
        self.monitoring_targets: List[str] = []
        self.active_scans: List[Dict[str, Any]] = []

        # Security performance metrics
        self.threats_detected = 0
        self.vulnerabilities_found = 0
        self.incidents_handled = 0
        self.false_positives = 0
        self.scan_completion_rate = 0.0

        # Last security activities
        self.last_threat_detection = None
        self.last_scan_completed = None
        self.last_incident_response = None
        self.last_vulnerability_assessment = None

        # Security tools state
        self.security_tools_status: Dict[str, str] = {
            "nuclei": "ready",
            "nmap": "ready",
            "subfinder": "ready",
            "httpx": "ready"
        }

        # Intelligence correlation state
        self.correlation_queue: List[Dict[str, Any]] = []
        self.pending_analysis: List[str] = []

        # Custom state variables
        self.custom_state: Dict[str, Any] = {}
    
    def update_status(self, new_status: AgentStatus):
        """Cập nhật status"""
        old_status = self.status
        self.status = new_status
        self.last_updated = datetime.utcnow()
        
        logger.debug(f"Agent status changed: {old_status.value} -> {new_status.value}")
    
    def update_mood(self, new_mood: AgentMood):
        """Cập nhật mood"""
        self.mood = new_mood
        self.last_updated = datetime.utcnow()
    
    def adjust_energy(self, delta: float):
        """Điều chỉnh energy level"""
        self.energy_level = max(0.0, min(1.0, self.energy_level + delta))
        self.last_updated = datetime.utcnow()
    
    def adjust_confidence(self, delta: float):
        """Điều chỉnh confidence level"""
        self.confidence_level = max(0.0, min(1.0, self.confidence_level + delta))
        self.last_updated = datetime.utcnow()
        
        # Adjust mood based on confidence
        if self.confidence_level > 0.8:
            self.mood = AgentMood.CONFIDENT
        elif self.confidence_level < 0.3:
            self.mood = AgentMood.UNCERTAIN
    
    def set_current_goal(self, goal_id: str):
        """Set current goal"""
        self.current_goal_id = goal_id
        self.last_updated = datetime.utcnow()
    
    def set_current_task(self, task: Dict[str, Any]):
        """Set current task"""
        self.current_task = task
        self.last_action = datetime.utcnow()
        self.last_updated = datetime.utcnow()
    
    def push_context(self, context: Dict[str, Any]):
        """Push context lên stack"""
        self.context_stack.append({
            **context,
            "timestamp": datetime.utcnow()
        })
    
    def pop_context(self) -> Optional[Dict[str, Any]]:
        """Pop context từ stack"""
        if self.context_stack:
            return self.context_stack.pop()
        return None
    
    def update(self, key: str, value: Any):
        """Update custom state variable"""
        self.custom_state[key] = value
        self.last_updated = datetime.utcnow()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get custom state variable"""
        return self.custom_state.get(key, default)
    
    def calculate_effectiveness(self) -> float:
        """Tính toán effectiveness tổng thể"""
        return (
            self.energy_level * 0.3 +
            self.confidence_level * 0.3 +
            self.focus_level * 0.2 +
            (1.0 - self.stress_level) * 0.2
        )
    
    def update_cognitive_load(self, load_delta: float):
        """Cập nhật cognitive load"""
        self.cognitive_load = max(0.0, min(1.0, self.cognitive_load + load_delta))
        
        # High cognitive load affects other states
        if self.cognitive_load > 0.8:
            self.stress_level = min(1.0, self.stress_level + 0.1)
            self.focus_level = max(0.0, self.focus_level - 0.1)
            self.mood = AgentMood.OVERWHELMED
    
    def reset_to_baseline(self):
        """Reset về baseline state"""
        self.status = AgentStatus.IDLE
        self.mood = AgentMood.CONFIDENT
        self.energy_level = 1.0
        self.confidence_level = 0.8
        self.focus_level = 0.8
        self.cognitive_load = 0.0
        self.stress_level = 0.0
        self.current_goal_id = None
        self.current_task = None
        self.context_stack.clear()
        self.last_updated = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize enhanced security state to dictionary"""
        return {
            # Basic agent state
            "status": self.status.value,
            "mood": self.mood.value,
            "energy_level": self.energy_level,
            "confidence_level": self.confidence_level,
            "focus_level": self.focus_level,
            "cognitive_load": self.cognitive_load,
            "stress_level": self.stress_level,
            "current_goal_id": self.current_goal_id,
            "current_task": self.current_task,
            "context_stack_size": len(self.context_stack),
            "recent_success_rate": self.recent_success_rate,
            "learning_rate": self.learning_rate,
            "effectiveness": self.calculate_effectiveness(),
            "last_updated": self.last_updated.isoformat(),
            "last_action": self.last_action.isoformat(),

            # Security-specific state
            "security_alert_level": self.security_alert_level.value,
            "threat_awareness_level": self.threat_awareness_level,
            "scan_activity_level": self.scan_activity_level,
            "active_threats": self.active_threats,
            "current_incident_id": self.current_incident_id,
            "monitoring_targets": self.monitoring_targets,
            "active_scans_count": len(self.active_scans),

            # Security performance metrics
            "threats_detected": self.threats_detected,
            "vulnerabilities_found": self.vulnerabilities_found,
            "incidents_handled": self.incidents_handled,
            "false_positives": self.false_positives,
            "scan_completion_rate": self.scan_completion_rate,

            # Security tools status
            "security_tools_status": self.security_tools_status,
            "correlation_queue_size": len(self.correlation_queue),
            "pending_analysis_count": len(self.pending_analysis),

            # Timestamps for security activities
            "last_threat_detection": self.last_threat_detection.isoformat() if self.last_threat_detection else None,
            "last_scan_completed": self.last_scan_completed.isoformat() if self.last_scan_completed else None,
            "last_incident_response": self.last_incident_response.isoformat() if self.last_incident_response else None,
            "last_vulnerability_assessment": self.last_vulnerability_assessment.isoformat() if self.last_vulnerability_assessment else None,

            "custom_state": self.custom_state
        }

    def update_security_alert_level(self, new_level: SecurityAlertLevel):
        """Update security alert level"""
        old_level = self.security_alert_level
        self.security_alert_level = new_level
        self.last_updated = datetime.utcnow()

        # Adjust agent mood and focus based on alert level
        if new_level == SecurityAlertLevel.RED:
            self.mood = AgentMood.ALERT
            self.focus_level = min(1.0, self.focus_level + 0.3)
            self.stress_level = min(1.0, self.stress_level + 0.4)
        elif new_level == SecurityAlertLevel.ORANGE:
            self.mood = AgentMood.VIGILANT
            self.focus_level = min(1.0, self.focus_level + 0.2)
            self.stress_level = min(1.0, self.stress_level + 0.2)
        elif new_level == SecurityAlertLevel.YELLOW:
            self.mood = AgentMood.CONCERNED
            self.focus_level = min(1.0, self.focus_level + 0.1)
        else:  # GREEN
            if self.mood in [AgentMood.ALERT, AgentMood.VIGILANT, AgentMood.CONCERNED]:
                self.mood = AgentMood.CONFIDENT

        logger.info(f"Security alert level changed: {old_level.value} -> {new_level.value}")

    def add_active_threat(self, threat_id: str):
        """Add threat to active threats list"""
        if threat_id not in self.active_threats:
            self.active_threats.append(threat_id)
            self.threats_detected += 1
            self.last_threat_detection = datetime.utcnow()
            self.threat_awareness_level = min(1.0, self.threat_awareness_level + 0.1)

            # Escalate alert level if needed
            if len(self.active_threats) >= 3:
                self.update_security_alert_level(SecurityAlertLevel.ORANGE)
            elif len(self.active_threats) >= 1:
                self.update_security_alert_level(SecurityAlertLevel.YELLOW)

            logger.warning(f"Added active threat: {threat_id}")

    def remove_active_threat(self, threat_id: str):
        """Remove threat from active threats list"""
        if threat_id in self.active_threats:
            self.active_threats.remove(threat_id)
            self.threat_awareness_level = max(0.0, self.threat_awareness_level - 0.1)

            # De-escalate alert level if appropriate
            if len(self.active_threats) == 0:
                self.update_security_alert_level(SecurityAlertLevel.GREEN)
            elif len(self.active_threats) < 3:
                self.update_security_alert_level(SecurityAlertLevel.YELLOW)

            logger.info(f"Removed active threat: {threat_id}")

    def start_scan(self, scan_data: Dict[str, Any]):
        """Register a new active scan"""
        scan_info = {
            "id": scan_data.get("id", f"scan_{datetime.utcnow().timestamp()}"),
            "type": scan_data.get("type", "unknown"),
            "target": scan_data.get("target", ""),
            "tool": scan_data.get("tool", ""),
            "started_at": datetime.utcnow(),
            "status": "running"
        }

        self.active_scans.append(scan_info)
        self.scan_activity_level = min(1.0, self.scan_activity_level + 0.2)
        self.status = AgentStatus.SCANNING

        logger.info(f"Started scan: {scan_info['id']}")

    def complete_scan(self, scan_id: str, vulnerabilities_found: int = 0):
        """Mark scan as completed"""
        for scan in self.active_scans:
            if scan["id"] == scan_id:
                scan["status"] = "completed"
                scan["completed_at"] = datetime.utcnow()
                self.last_scan_completed = datetime.utcnow()
                self.vulnerabilities_found += vulnerabilities_found
                break

        # Clean up completed scans
        self.active_scans = [s for s in self.active_scans if s["status"] == "running"]
        self.scan_activity_level = max(0.0, self.scan_activity_level - 0.2)

        # Update scan completion rate
        total_scans = self.custom_state.get("total_scans", 0) + 1
        completed_scans = self.custom_state.get("completed_scans", 0) + 1
        self.scan_completion_rate = completed_scans / total_scans
        self.custom_state["total_scans"] = total_scans
        self.custom_state["completed_scans"] = completed_scans

        if not self.active_scans:
            self.status = AgentStatus.IDLE

        logger.info(f"Completed scan: {scan_id}, vulnerabilities found: {vulnerabilities_found}")

    def start_incident_response(self, incident_id: str):
        """Start incident response"""
        self.current_incident_id = incident_id
        self.status = AgentStatus.RESPONDING_TO_INCIDENT
        self.last_incident_response = datetime.utcnow()
        self.focus_level = min(1.0, self.focus_level + 0.3)

        logger.warning(f"Started incident response: {incident_id}")

    def complete_incident_response(self):
        """Complete incident response"""
        if self.current_incident_id:
            self.incidents_handled += 1
            self.current_incident_id = None
            self.status = AgentStatus.IDLE

            logger.info("Completed incident response")

    def update_security_tool_status(self, tool_name: str, status: str):
        """Update security tool status"""
        if tool_name in self.security_tools_status:
            old_status = self.security_tools_status[tool_name]
            self.security_tools_status[tool_name] = status

            logger.debug(f"Tool {tool_name} status: {old_status} -> {status}")

    def add_monitoring_target(self, target: str):
        """Add target to monitoring list"""
        if target not in self.monitoring_targets:
            self.monitoring_targets.append(target)
            logger.info(f"Added monitoring target: {target}")

    def remove_monitoring_target(self, target: str):
        """Remove target from monitoring list"""
        if target in self.monitoring_targets:
            self.monitoring_targets.remove(target)
            logger.info(f"Removed monitoring target: {target}")

    def add_to_correlation_queue(self, correlation_data: Dict[str, Any]):
        """Add data to correlation queue"""
        self.correlation_queue.append({
            **correlation_data,
            "queued_at": datetime.utcnow()
        })

        # Limit queue size
        if len(self.correlation_queue) > 100:
            self.correlation_queue = self.correlation_queue[-100:]

    def add_pending_analysis(self, analysis_id: str):
        """Add analysis to pending queue"""
        if analysis_id not in self.pending_analysis:
            self.pending_analysis.append(analysis_id)

    def complete_analysis(self, analysis_id: str):
        """Mark analysis as completed"""
        if analysis_id in self.pending_analysis:
            self.pending_analysis.remove(analysis_id)

    def record_false_positive(self):
        """Record a false positive detection"""
        self.false_positives += 1
        self.confidence_level = max(0.0, self.confidence_level - 0.05)

    def get_security_readiness_score(self) -> float:
        """Calculate security readiness score"""
        readiness_factors = [
            self.energy_level * 0.2,
            self.confidence_level * 0.2,
            self.focus_level * 0.2,
            (1.0 - self.stress_level) * 0.15,
            self.threat_awareness_level * 0.15,
            (1.0 - self.cognitive_load) * 0.1
        ]

        return sum(readiness_factors)

    def get_security_performance_summary(self) -> Dict[str, Any]:
        """Get security performance summary"""
        return {
            "threats_detected": self.threats_detected,
            "vulnerabilities_found": self.vulnerabilities_found,
            "incidents_handled": self.incidents_handled,
            "false_positives": self.false_positives,
            "scan_completion_rate": self.scan_completion_rate,
            "security_readiness_score": self.get_security_readiness_score(),
            "active_threats_count": len(self.active_threats),
            "active_scans_count": len(self.active_scans),
            "monitoring_targets_count": len(self.monitoring_targets),
            "security_alert_level": self.security_alert_level.value
        }