from typing import Dict, Any, List, Optional, Callable
import logging
from datetime import datetime
import re
import json
from enum import Enum

logger = logging.getLogger("agents")


class SensorType(Enum):
    """Types of security sensors for OASM agents"""
    NETWORK_SENSOR = "network_sensor"
    VULNERABILITY_SENSOR = "vulnerability_sensor"
    THREAT_INTEL_SENSOR = "threat_intel_sensor"
    LOG_SENSOR = "log_sensor"
    IOC_SENSOR = "ioc_sensor"
    SCAN_RESULT_SENSOR = "scan_result_sensor"


class PerceptionSystem:
    """Security-focused perception system for OASM agents"""

    def __init__(self, agent):
        self.agent = agent
        self.sensors: List[str] = []  # Available security sensors
        self.perception_filters: List[Callable] = []  # Security-focused filters
        self.last_perception: Optional[Dict[str, Any]] = None

        # Security-specific perception components
        self.threat_patterns: List[Dict[str, Any]] = []
        self.vulnerability_signatures: List[Dict[str, Any]] = []
        self.ioc_patterns: List[Dict[str, Any]] = []

        # Initialize default security sensors
        self._initialize_security_sensors()
        
    def add_sensor(self, sensor_name: str):
        """Thêm sensor"""
        self.sensors.append(sensor_name)
        logger.debug(f"Added sensor '{sensor_name}' to agent {self.agent.name}")
    
    def add_filter(self, filter_func: callable):
        """Thêm perception filter"""
        self.perception_filters.append(filter_func)
    
    def perceive(self) -> Dict[str, Any]:
        """Nhận thức environment"""
        raw_observations = self._gather_raw_observations()
        filtered_observations = self._apply_filters(raw_observations)
        processed_observations = self._process_observations(filtered_observations)
        
        self.last_perception = processed_observations
        return processed_observations
    
    def _gather_raw_observations(self) -> Dict[str, Any]:
        """Thu thập raw observations"""
        observations = {
            "timestamp": datetime.utcnow(),
            "environment_state": self.agent.environment.get_environment_state(),
            "agent_state": self.agent.state.to_dict(),
            "available_resources": list(self.agent.environment.shared_resources.keys()),
            "messages": self.agent.environment.get_messages(self.agent.id)
        }
        
        return observations
    
    def _apply_filters(self, observations: Dict[str, Any]) -> Dict[str, Any]:
        """Áp dụng perception filters"""
        filtered_obs = observations.copy()
        
        for filter_func in self.perception_filters:
            try:
                filtered_obs = filter_func(filtered_obs)
            except Exception as e:
                logger.error(f"Perception filter error: {e}")
        
        return filtered_obs
    
    def _process_observations(self, observations: Dict[str, Any]) -> Dict[str, Any]:
        """Xử lý observations"""
        processed = {
            "raw_observations": observations,
            "relevant_changes": self._detect_changes(observations),
            "attention_focus": self._determine_attention_focus(observations),
            "threat_level": self._assess_threat_level(observations)
        }
        
        return processed
    
    def _detect_changes(self, observations: Dict[str, Any]) -> List[str]:
        """Phát hiện thay đổi từ lần perception trước"""
        changes = []
        
        if self.last_perception:
            # Compare with last perception
            if observations["environment_state"] != self.last_perception.get("raw_observations", {}).get("environment_state"):
                changes.append("environment_changed")
            
            if len(observations["messages"]) > len(self.last_perception.get("raw_observations", {}).get("messages", [])):
                changes.append("new_messages")
        
        return changes
    
    def _determine_attention_focus(self, observations: Dict[str, Any]) -> List[str]:
        """Xác định trọng tâm attention"""
        focus_areas = []
        
        # Focus on new messages
        if observations["messages"]:
            focus_areas.append("communication")
        
        # Focus on environment changes
        if self._detect_changes(observations):
            focus_areas.append("environment_monitoring")
        
        return focus_areas
    
    def _assess_threat_level(self, observations: Dict[str, Any]) -> str:
        """Assess threat level based on security observations"""
        threat_score = 0
        obs_str = str(observations).lower()

        # Critical security indicators
        critical_indicators = ["malware", "exploit", "breach", "compromise", "attack", "intrusion"]
        high_indicators = ["vulnerability", "suspicious", "anomaly", "unauthorized", "failed_login"]
        medium_indicators = ["warning", "alert", "unusual", "unexpected"]

        for indicator in critical_indicators:
            if indicator in obs_str:
                threat_score += 3

        for indicator in high_indicators:
            if indicator in obs_str:
                threat_score += 2

        for indicator in medium_indicators:
            if indicator in obs_str:
                threat_score += 1

        # Assess based on environment threat level
        env_threat_level = observations.get("environment_state", {}).get("threat_level", "low")
        if env_threat_level == "critical":
            threat_score += 4
        elif env_threat_level == "high":
            threat_score += 3
        elif env_threat_level == "medium":
            threat_score += 2

        # Determine final threat level
        if threat_score >= 8:
            return "critical"
        elif threat_score >= 5:
            return "high"
        elif threat_score >= 2:
            return "medium"
        else:
            return "low"

    def _initialize_security_sensors(self):
        """Initialize default security sensors"""
        default_sensors = [
            SensorType.NETWORK_SENSOR.value,
            SensorType.VULNERABILITY_SENSOR.value,
            SensorType.THREAT_INTEL_SENSOR.value,
            SensorType.IOC_SENSOR.value
        ]

        for sensor in default_sensors:
            self.add_sensor(sensor)

        # Add default security filters
        self.add_filter(self._filter_security_noise)
        self.add_filter(self._filter_high_priority_threats)

    def add_threat_pattern(self, pattern: Dict[str, Any]):
        """Add threat detection pattern"""
        self.threat_patterns.append({
            "id": pattern.get("id", f"pattern_{len(self.threat_patterns)}"),
            "name": pattern.get("name", "unknown"),
            "regex": pattern.get("regex", ""),
            "severity": pattern.get("severity", "medium"),
            "description": pattern.get("description", ""),
            "indicators": pattern.get("indicators", [])
        })

        logger.debug(f"Added threat pattern: {pattern.get('name')}")

    def add_vulnerability_signature(self, signature: Dict[str, Any]):
        """Add vulnerability detection signature"""
        self.vulnerability_signatures.append({
            "id": signature.get("id", f"vuln_{len(self.vulnerability_signatures)}"),
            "cve_id": signature.get("cve_id", ""),
            "signature": signature.get("signature", ""),
            "severity": signature.get("severity", "medium"),
            "description": signature.get("description", "")
        })

        logger.debug(f"Added vulnerability signature: {signature.get('cve_id')}")

    def add_ioc_pattern(self, ioc_pattern: Dict[str, Any]):
        """Add IOC detection pattern"""
        self.ioc_patterns.append({
            "id": ioc_pattern.get("id", f"ioc_{len(self.ioc_patterns)}"),
            "type": ioc_pattern.get("type", "unknown"),
            "pattern": ioc_pattern.get("pattern", ""),
            "confidence": ioc_pattern.get("confidence", 0.5),
            "source": ioc_pattern.get("source", "manual")
        })

        logger.debug(f"Added IOC pattern: {ioc_pattern.get('type')}")

    def detect_threats(self, data: str) -> List[Dict[str, Any]]:
        """Detect threats using configured patterns"""
        detected_threats = []

        for pattern in self.threat_patterns:
            if pattern["regex"]:
                try:
                    matches = re.findall(pattern["regex"], data, re.IGNORECASE)
                    if matches:
                        detected_threats.append({
                            "pattern_id": pattern["id"],
                            "pattern_name": pattern["name"],
                            "severity": pattern["severity"],
                            "matches": matches,
                            "confidence": 0.8
                        })
                except re.error as e:
                    logger.error(f"Regex error in pattern {pattern['id']}: {e}")

        return detected_threats

    def detect_vulnerabilities(self, scan_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect vulnerabilities using signatures"""
        detected_vulns = []
        scan_text = json.dumps(scan_data).lower()

        for signature in self.vulnerability_signatures:
            if signature["signature"] in scan_text:
                detected_vulns.append({
                    "signature_id": signature["id"],
                    "cve_id": signature["cve_id"],
                    "severity": signature["severity"],
                    "description": signature["description"],
                    "confidence": 0.9
                })

        return detected_vulns

    def detect_iocs(self, data: str) -> List[Dict[str, Any]]:
        """Detect IOCs using patterns"""
        detected_iocs = []

        for ioc_pattern in self.ioc_patterns:
            try:
                matches = re.findall(ioc_pattern["pattern"], data, re.IGNORECASE)
                if matches:
                    detected_iocs.append({
                        "pattern_id": ioc_pattern["id"],
                        "type": ioc_pattern["type"],
                        "matches": matches,
                        "confidence": ioc_pattern["confidence"],
                        "source": ioc_pattern["source"]
                    })
            except re.error as e:
                logger.error(f"Regex error in IOC pattern {ioc_pattern['id']}: {e}")

        return detected_iocs

    def _filter_security_noise(self, observations: Dict[str, Any]) -> Dict[str, Any]:
        """Filter out security noise and irrelevant data"""
        filtered_obs = observations.copy()

        # Remove low-priority or informational messages
        if "messages" in filtered_obs:
            filtered_obs["messages"] = [
                msg for msg in filtered_obs["messages"]
                if not self._is_security_noise(msg)
            ]

        return filtered_obs

    def _filter_high_priority_threats(self, observations: Dict[str, Any]) -> Dict[str, Any]:
        """Prioritize high-severity threats"""
        filtered_obs = observations.copy()

        # Boost priority for critical security events
        env_state = filtered_obs.get("environment_state", {})
        if env_state.get("threat_level") in ["high", "critical"]:
            filtered_obs["priority_boost"] = True

        return filtered_obs

    def _is_security_noise(self, message: Dict[str, Any]) -> bool:
        """Determine if a message is security noise"""
        content = str(message).lower()
        noise_indicators = ["info", "debug", "trace", "heartbeat", "keepalive"]

        return any(indicator in content for indicator in noise_indicators)

    def analyze_security_context(self, observations: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze security context from observations"""
        context = {
            "threat_indicators": [],
            "vulnerabilities": [],
            "iocs": [],
            "security_events": [],
            "risk_assessment": "low"
        }

        # Extract raw data for analysis
        obs_text = json.dumps(observations)

        # Detect threats
        context["threat_indicators"] = self.detect_threats(obs_text)

        # Detect IOCs
        context["iocs"] = self.detect_iocs(obs_text)

        # Check for scan results
        scan_results = observations.get("environment_state", {}).get("scan_results", {})
        for scan_id, scan_data in scan_results.items():
            if not scan_data.get("processed", False):
                context["vulnerabilities"].extend(self.detect_vulnerabilities(scan_data))

        # Security events from environment
        security_events = observations.get("environment_state", {}).get("security_events", [])
        context["security_events"] = security_events[-5:]  # Last 5 events

        # Risk assessment
        context["risk_assessment"] = self._assess_overall_risk(context)

        return context

    def _assess_overall_risk(self, security_context: Dict[str, Any]) -> str:
        """Assess overall security risk"""
        risk_score = 0

        # Count high-severity indicators
        for threat in security_context.get("threat_indicators", []):
            if threat.get("severity") == "critical":
                risk_score += 5
            elif threat.get("severity") == "high":
                risk_score += 3
            else:
                risk_score += 1

        # Count vulnerabilities
        for vuln in security_context.get("vulnerabilities", []):
            if vuln.get("severity") == "critical":
                risk_score += 4
            elif vuln.get("severity") == "high":
                risk_score += 2
            else:
                risk_score += 1

        # Count high-confidence IOCs
        high_conf_iocs = [
            ioc for ioc in security_context.get("iocs", [])
            if ioc.get("confidence", 0) > 0.7
        ]
        risk_score += len(high_conf_iocs)

        # Determine risk level
        if risk_score >= 10:
            return "critical"
        elif risk_score >= 6:
            return "high"
        elif risk_score >= 3:
            return "medium"
        else:
            return "low"
