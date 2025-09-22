from typing import Dict, Any, List, Optional
import asyncio
import logging
from datetime import datetime
from enum import Enum
import json

logger = logging.getLogger("agents")


class ThreatLevel(Enum):
    """Threat levels for OASM environment monitoring"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EnvironmentEvent(Enum):
    """Types of security events in the environment"""
    THREAT_DETECTED = "threat_detected"
    SCAN_COMPLETED = "scan_completed"
    VULNERABILITY_FOUND = "vulnerability_found"
    AGENT_COMMUNICATION = "agent_communication"
    RESOURCE_ACCESS = "resource_access"
    SYSTEM_ALERT = "system_alert"


class AgentEnvironment:
    """Security-focused environment for OASM agents with threat monitoring"""

    def __init__(self):
        self.agents: Dict[str, Any] = {}  # Registered security agents
        self.shared_resources: Dict[str, Any] = {}  # Security tools and databases
        self.communication_channels: Dict[str, List] = {}  # Agent communication

        # OASM-specific environment state
        self.environmental_state: Dict[str, Any] = {
            "timestamp": datetime.utcnow(),
            "active_agents": 0,
            "resource_utilization": {},
            "threat_level": ThreatLevel.LOW.value,
            "active_threats": [],
            "scan_results": {},
            "vulnerability_database": {},
            "ioc_database": {},  # Indicators of Compromise
            "network_topology": {},
            "security_events": []
        }

        # Threat intelligence and security context
        self.threat_intelligence: Dict[str, Any] = {
            "known_threats": [],
            "threat_feeds": [],
            "vulnerability_feeds": [],
            "ioc_feeds": []
        }

        # Security tools integration
        self.security_tools: Dict[str, Any] = {
            "nuclei": {"available": True, "templates_loaded": False},
            "nmap": {"available": True, "scan_profiles": []},
            "subfinder": {"available": True, "wordlists": []},
            "httpx": {"available": True, "probe_configs": []}
        }

        logger.info("OASM security environment initialized")
    
    def register_agent(self, agent: Any):
        """Đăng ký agent vào environment"""
        self.agents[agent.id] = {
            "agent": agent,
            "registered_at": datetime.utcnow(),
            "last_activity": datetime.utcnow()
        }
        self.environmental_state["active_agents"] = len(self.agents)
        logger.info(f"Agent {agent.name} registered in environment")
    
    def unregister_agent(self, agent_id: str):
        """Hủy đăng ký agent"""
        if agent_id in self.agents:
            agent_name = self.agents[agent_id]["agent"].name
            del self.agents[agent_id]
            self.environmental_state["active_agents"] = len(self.agents)
            logger.info(f"Agent {agent_name} unregistered from environment")
    
    def get_agent(self, agent_id: str) -> Optional[Any]:
        """Lấy agent theo ID"""
        agent_info = self.agents.get(agent_id)
        return agent_info["agent"] if agent_info else None
    
    def list_agents(self) -> List[Dict[str, Any]]:
        """Liệt kê tất cả agents"""
        return [
            {
                "id": agent_id,
                "name": info["agent"].name,
                "role": info["agent"].role.value,
                "registered_at": info["registered_at"],
                "last_activity": info["last_activity"]
            }
            for agent_id, info in self.agents.items()
        ]
    
    def add_shared_resource(self, name: str, resource: Any):
        """Thêm shared resource"""
        self.shared_resources[name] = {
            "resource": resource,
            "created_at": datetime.utcnow(),
            "access_count": 0
        }
        logger.info(f"Shared resource '{name}' added to environment")
    
    def get_shared_resource(self, name: str) -> Optional[Any]:
        """Lấy shared resource"""
        if name in self.shared_resources:
            self.shared_resources[name]["access_count"] += 1
            return self.shared_resources[name]["resource"]
        return None
    
    def send_message(self, from_agent_id: str, to_agent_id: str, message: Dict[str, Any]):
        """Gửi message giữa agents"""
        channel_key = f"{from_agent_id}->{to_agent_id}"
        if channel_key not in self.communication_channels:
            self.communication_channels[channel_key] = []
        
        message_with_metadata = {
            **message,
            "timestamp": datetime.utcnow(),
            "from": from_agent_id,
            "to": to_agent_id
        }
        
        self.communication_channels[channel_key].append(message_with_metadata)
        logger.debug(f"Message sent from {from_agent_id} to {to_agent_id}")
    
    def get_messages(self, agent_id: str) -> List[Dict[str, Any]]:
        """Lấy messages cho agent"""
        messages = []
        for channel_key, channel_messages in self.communication_channels.items():
            if channel_key.endswith(f"->{agent_id}"):
                messages.extend(channel_messages)
        
        return sorted(messages, key=lambda x: x["timestamp"])
    
    def get_environment_state(self) -> Dict[str, Any]:
        """Get current security environment state"""
        self.environmental_state.update({
            "timestamp": datetime.utcnow(),
            "active_agents": len(self.agents),
            "shared_resources_count": len(self.shared_resources),
            "communication_channels": len(self.communication_channels),
            "security_tools_available": len([tool for tool, config in self.security_tools.items() if config["available"]]),
            "active_threats_count": len(self.environmental_state["active_threats"]),
            "recent_events_count": len(self.environmental_state["security_events"][-10:])
        })

        return self.environmental_state

    def add_threat(self, threat_data: Dict[str, Any]):
        """Add new threat to environment tracking"""
        threat = {
            "id": threat_data.get("id", f"threat_{datetime.utcnow().timestamp()}"),
            "type": threat_data.get("type", "unknown"),
            "severity": threat_data.get("severity", "medium"),
            "description": threat_data.get("description", ""),
            "indicators": threat_data.get("indicators", []),
            "detected_at": datetime.utcnow(),
            "status": "active"
        }

        self.environmental_state["active_threats"].append(threat)
        self._update_threat_level()
        self._log_security_event(EnvironmentEvent.THREAT_DETECTED, threat)

        logger.warning(f"New threat added: {threat['type']} - {threat['severity']}")

    def resolve_threat(self, threat_id: str):
        """Mark threat as resolved"""
        for threat in self.environmental_state["active_threats"]:
            if threat["id"] == threat_id:
                threat["status"] = "resolved"
                threat["resolved_at"] = datetime.utcnow()
                break

        # Remove resolved threats
        self.environmental_state["active_threats"] = [
            t for t in self.environmental_state["active_threats"] if t["status"] == "active"
        ]

        self._update_threat_level()
        logger.info(f"Threat {threat_id} resolved")

    def add_scan_result(self, scan_id: str, scan_data: Dict[str, Any]):
        """Add security scan results to environment"""
        self.environmental_state["scan_results"][scan_id] = {
            **scan_data,
            "timestamp": datetime.utcnow(),
            "processed": False
        }

        self._log_security_event(EnvironmentEvent.SCAN_COMPLETED, {"scan_id": scan_id})

        # Check for vulnerabilities in scan results
        if scan_data.get("vulnerabilities"):
            for vuln in scan_data["vulnerabilities"]:
                self.add_vulnerability(vuln)

        logger.info(f"Scan results added: {scan_id}")

    def add_vulnerability(self, vulnerability_data: Dict[str, Any]):
        """Add vulnerability to database"""
        vuln_id = vulnerability_data.get("id", f"vuln_{datetime.utcnow().timestamp()}")

        vulnerability = {
            "id": vuln_id,
            "cve_id": vulnerability_data.get("cve_id"),
            "severity": vulnerability_data.get("severity", "medium"),
            "title": vulnerability_data.get("title", ""),
            "description": vulnerability_data.get("description", ""),
            "affected_systems": vulnerability_data.get("affected_systems", []),
            "discovered_at": datetime.utcnow(),
            "status": "open"
        }

        self.environmental_state["vulnerability_database"][vuln_id] = vulnerability
        self._log_security_event(EnvironmentEvent.VULNERABILITY_FOUND, vulnerability)

        logger.warning(f"Vulnerability added: {vuln_id} - {vulnerability['severity']}")

    def add_ioc(self, ioc_data: Dict[str, Any]):
        """Add Indicator of Compromise to database"""
        ioc_id = ioc_data.get("id", f"ioc_{datetime.utcnow().timestamp()}")

        ioc = {
            "id": ioc_id,
            "type": ioc_data.get("type", "unknown"),  # ip, domain, hash, etc.
            "value": ioc_data.get("value", ""),
            "confidence": ioc_data.get("confidence", 0.5),
            "source": ioc_data.get("source", "manual"),
            "added_at": datetime.utcnow(),
            "last_seen": ioc_data.get("last_seen"),
            "tags": ioc_data.get("tags", [])
        }

        self.environmental_state["ioc_database"][ioc_id] = ioc
        logger.info(f"IOC added: {ioc_id} - {ioc['type']}")

    def get_security_tools_status(self) -> Dict[str, Any]:
        """Get status of security tools"""
        return self.security_tools

    def update_security_tool_status(self, tool_name: str, status_update: Dict[str, Any]):
        """Update security tool status"""
        if tool_name in self.security_tools:
            self.security_tools[tool_name].update(status_update)
            logger.info(f"Updated {tool_name} status: {status_update}")

    def get_threat_intelligence(self) -> Dict[str, Any]:
        """Get current threat intelligence"""
        return self.threat_intelligence

    def update_threat_intelligence(self, intel_type: str, data: List[Dict[str, Any]]):
        """Update threat intelligence feeds"""
        if intel_type in self.threat_intelligence:
            self.threat_intelligence[intel_type].extend(data)
            logger.info(f"Updated threat intelligence: {intel_type} - {len(data)} items")

    def query_vulnerabilities(self, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Query vulnerability database with filters"""
        vulns = list(self.environmental_state["vulnerability_database"].values())

        if not filters:
            return vulns

        # Apply filters
        if "severity" in filters:
            vulns = [v for v in vulns if v["severity"] == filters["severity"]]
        if "status" in filters:
            vulns = [v for v in vulns if v["status"] == filters["status"]]

        return vulns

    def query_iocs(self, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Query IOC database with filters"""
        iocs = list(self.environmental_state["ioc_database"].values())

        if not filters:
            return iocs

        # Apply filters
        if "type" in filters:
            iocs = [i for i in iocs if i["type"] == filters["type"]]
        if "min_confidence" in filters:
            iocs = [i for i in iocs if i["confidence"] >= filters["min_confidence"]]

        return iocs

    def _update_threat_level(self):
        """Update overall threat level based on active threats"""
        active_threats = self.environmental_state["active_threats"]

        if not active_threats:
            self.environmental_state["threat_level"] = ThreatLevel.LOW.value
            return

        # Calculate threat level based on severity and count
        high_severity_count = len([t for t in active_threats if t["severity"] == "high"])
        critical_count = len([t for t in active_threats if t["severity"] == "critical"])

        if critical_count > 0:
            self.environmental_state["threat_level"] = ThreatLevel.CRITICAL.value
        elif high_severity_count > 2:
            self.environmental_state["threat_level"] = ThreatLevel.HIGH.value
        elif len(active_threats) > 5:
            self.environmental_state["threat_level"] = ThreatLevel.MEDIUM.value
        else:
            self.environmental_state["threat_level"] = ThreatLevel.LOW.value

    def _log_security_event(self, event_type: EnvironmentEvent, event_data: Dict[str, Any]):
        """Log security events for audit trail"""
        event = {
            "type": event_type.value,
            "timestamp": datetime.utcnow(),
            "data": event_data,
            "environment_state_snapshot": {
                "threat_level": self.environmental_state["threat_level"],
                "active_agents": len(self.agents),
                "active_threats": len(self.environmental_state["active_threats"])
            }
        }

        self.environmental_state["security_events"].append(event)

        # Keep only last 1000 events to prevent memory issues
        if len(self.environmental_state["security_events"]) > 1000:
            self.environmental_state["security_events"] = self.environmental_state["security_events"][-1000:]

    def get_security_events(self, limit: int = 50, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recent security events"""
        events = self.environmental_state["security_events"]

        if event_type:
            events = [e for e in events if e["type"] == event_type]

        return events[-limit:] if limit else events
