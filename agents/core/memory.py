from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json
from collections import deque
import logging
from enum import Enum

logger = logging.getLogger("agents")


class MemoryType(Enum):
    """Types of memory for OASM security agents"""
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    THREAT_INTELLIGENCE = "threat_intelligence"
    VULNERABILITY_DATABASE = "vulnerability_database"
    IOC_DATABASE = "ioc_database"
    SCAN_HISTORY = "scan_history"


class ThreatIntelligenceType(Enum):
    """Types of threat intelligence data"""
    IOC = "ioc"
    TTP = "ttp"  # Tactics, Techniques, and Procedures
    CAMPAIGN = "campaign"
    ACTOR = "actor"
    MALWARE = "malware"
    VULNERABILITY = "vulnerability"


class AgentMemory:
    """Security-focused memory system for OASM agents"""

    def __init__(self, agent_id: str, max_working_memory: int = 100):
        self.agent_id = agent_id
        self.max_working_memory = max_working_memory

        # Different types of memory
        self.working_memory = deque(maxlen=max_working_memory)  # Recent observations/actions
        self.episodic_memory: List[Dict[str, Any]] = []  # Specific security experiences
        self.semantic_memory: Dict[str, Any] = {}  # General security knowledge
        self.procedural_memory: Dict[str, Any] = {}  # Security procedures and playbooks

        # Security-specific memory components
        self.threat_intelligence: Dict[str, List[Dict[str, Any]]] = {
            ThreatIntelligenceType.IOC.value: [],
            ThreatIntelligenceType.TTP.value: [],
            ThreatIntelligenceType.CAMPAIGN.value: [],
            ThreatIntelligenceType.ACTOR.value: [],
            ThreatIntelligenceType.MALWARE.value: [],
            ThreatIntelligenceType.VULNERABILITY.value: []
        }

        self.vulnerability_database: Dict[str, Dict[str, Any]] = {}
        self.ioc_database: Dict[str, Dict[str, Any]] = {}
        self.scan_history: List[Dict[str, Any]] = []
        self.incident_history: List[Dict[str, Any]] = []
        self.remediation_actions: List[Dict[str, Any]] = []

        logger.debug(f"OASM security memory system initialized for agent {agent_id}")
    
    def add_observation(self, observation: Dict[str, Any]):
        """Thêm observation vào working memory"""
        memory_item = {
            "type": "observation",
            "content": observation,
            "timestamp": datetime.utcnow(),
            "importance": self._calculate_importance(observation)
        }
        
        self.working_memory.append(memory_item)
    
    def add_action(self, action: Dict[str, Any], result: Dict[str, Any]):
        """Thêm action và result vào memory"""
        memory_item = {
            "type": "action",
            "action": action,
            "result": result,
            "timestamp": datetime.utcnow(),
            "success": result.get("success", False)
        }
        
        self.working_memory.append(memory_item)
    
    def add_experience(self, experience: Dict[str, Any]):
        """Thêm experience vào episodic memory"""
        episodic_item = {
            "id": len(self.episodic_memory),
            "content": experience,
            "timestamp": datetime.utcnow(),
            "tags": experience.get("tags", []),
            "outcome": experience.get("outcome")
        }
        
        self.episodic_memory.append(episodic_item)
        
        # Consolidate to semantic memory if pattern is found
        self._consolidate_to_semantic(episodic_item)
    
    def add_knowledge(self, knowledge_type: str, content: Dict[str, Any]):
        """Thêm knowledge vào semantic memory"""
        if knowledge_type not in self.semantic_memory:
            self.semantic_memory[knowledge_type] = []
        
        knowledge_item = {
            "content": content,
            "timestamp": datetime.utcnow(),
            "confidence": content.get("confidence", 1.0)
        }
        
        self.semantic_memory[knowledge_type].append(knowledge_item)
    
    def add_procedure(self, procedure_name: str, procedure: Dict[str, Any]):
        """Thêm procedure vào procedural memory"""
        self.procedural_memory[procedure_name] = {
            "steps": procedure.get("steps", []),
            "conditions": procedure.get("conditions", {}),
            "success_rate": procedure.get("success_rate", 0.0),
            "last_used": datetime.utcnow(),
            "usage_count": 0
        }
    
    def recall_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Recall recent memories từ working memory"""
        return list(self.working_memory)[-limit:]
    
    def recall_by_type(self, memory_type: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Recall memories theo type"""
        memories = [item for item in self.working_memory if item.get("type") == memory_type]
        return memories[-limit:]
    
    def recall_experiences(self, tags: List[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Recall experiences từ episodic memory"""
        if not tags:
            return self.episodic_memory[-limit:]
        
        relevant_experiences = []
        for exp in self.episodic_memory:
            if any(tag in exp.get("tags", []) for tag in tags):
                relevant_experiences.append(exp)
        
        return relevant_experiences[-limit:]
    
    def get_knowledge(self, knowledge_type: str) -> List[Dict[str, Any]]:
        """Lấy knowledge từ semantic memory"""
        return self.semantic_memory.get(knowledge_type, [])
    
    def get_procedure(self, procedure_name: str) -> Optional[Dict[str, Any]]:
        """Lấy procedure từ procedural memory"""
        if procedure_name in self.procedural_memory:
            procedure = self.procedural_memory[procedure_name]
            procedure["usage_count"] += 1
            procedure["last_used"] = datetime.utcnow()
            return procedure
        return None
    
    def _calculate_importance(self, observation: Dict[str, Any]) -> float:
        """Tính importance score cho observation"""
        importance = 0.5  # Base importance
        
        # Increase importance for certain types
        if "threat" in str(observation).lower():
            importance += 0.3
        if "error" in str(observation).lower():
            importance += 0.2
        if "success" in str(observation).lower():
            importance += 0.1
        
        return min(importance, 1.0)
    
    def _consolidate_to_semantic(self, experience: Dict[str, Any]):
        """Consolidate experience thành semantic knowledge"""
        # Simple pattern detection
        outcome = experience.get("outcome")
        if outcome:
            knowledge_type = f"experience_patterns"
            
            pattern = {
                "context": experience.get("content", {}).get("context"),
                "outcome": outcome,
                "frequency": 1
            }
            
            self.add_knowledge(knowledge_type, pattern)
    
    def cleanup_old_memories(self, days_old: int = 30):
        """Cleanup old memories"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        # Clean episodic memory
        self.episodic_memory = [
            exp for exp in self.episodic_memory 
            if exp["timestamp"] > cutoff_date
        ]
        
        logger.info(f"Cleaned up old memories for agent {self.agent_id}")
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get comprehensive memory statistics for security operations"""
        return {
            "working_memory_size": len(self.working_memory),
            "episodic_memory_size": len(self.episodic_memory),
            "semantic_knowledge_types": len(self.semantic_memory),
            "procedures_count": len(self.procedural_memory),
            "total_knowledge_items": sum(len(items) for items in self.semantic_memory.values()),
            # Security-specific stats
            "threat_intel_items": sum(len(items) for items in self.threat_intelligence.values()),
            "vulnerability_count": len(self.vulnerability_database),
            "ioc_count": len(self.ioc_database),
            "scan_history_count": len(self.scan_history),
            "incident_count": len(self.incident_history),
            "remediation_actions_count": len(self.remediation_actions)
        }

    def add_threat_intelligence(self, intel_type: str, data: Dict[str, Any]):
        """Add threat intelligence data"""
        if intel_type not in self.threat_intelligence:
            logger.warning(f"Unknown threat intelligence type: {intel_type}")
            return

        intel_item = {
            "id": data.get("id", f"{intel_type}_{datetime.utcnow().timestamp()}"),
            "data": data,
            "added_at": datetime.utcnow(),
            "source": data.get("source", "unknown"),
            "confidence": data.get("confidence", 0.5),
            "last_seen": data.get("last_seen"),
            "tags": data.get("tags", [])
        }

        self.threat_intelligence[intel_type].append(intel_item)
        logger.info(f"Added threat intelligence: {intel_type} - {intel_item['id']}")

    def add_vulnerability(self, vulnerability_data: Dict[str, Any]):
        """Add vulnerability to database"""
        vuln_id = vulnerability_data.get("id", f"vuln_{datetime.utcnow().timestamp()}")

        vulnerability = {
            "id": vuln_id,
            "cve_id": vulnerability_data.get("cve_id"),
            "severity": vulnerability_data.get("severity", "medium"),
            "cvss_score": vulnerability_data.get("cvss_score"),
            "title": vulnerability_data.get("title", ""),
            "description": vulnerability_data.get("description", ""),
            "affected_systems": vulnerability_data.get("affected_systems", []),
            "discovered_at": datetime.utcnow(),
            "status": vulnerability_data.get("status", "open"),
            "remediation": vulnerability_data.get("remediation", ""),
            "references": vulnerability_data.get("references", []),
            "tags": vulnerability_data.get("tags", [])
        }

        self.vulnerability_database[vuln_id] = vulnerability
        logger.info(f"Added vulnerability: {vuln_id}")

    def add_ioc(self, ioc_data: Dict[str, Any]):
        """Add Indicator of Compromise"""
        ioc_id = ioc_data.get("id", f"ioc_{datetime.utcnow().timestamp()}")

        ioc = {
            "id": ioc_id,
            "type": ioc_data.get("type", "unknown"),  # ip, domain, hash, url, etc.
            "value": ioc_data.get("value", ""),
            "confidence": ioc_data.get("confidence", 0.5),
            "severity": ioc_data.get("severity", "medium"),
            "source": ioc_data.get("source", "manual"),
            "added_at": datetime.utcnow(),
            "last_seen": ioc_data.get("last_seen"),
            "first_seen": ioc_data.get("first_seen"),
            "tags": ioc_data.get("tags", []),
            "context": ioc_data.get("context", {}),
            "related_threats": ioc_data.get("related_threats", [])
        }

        self.ioc_database[ioc_id] = ioc
        logger.info(f"Added IOC: {ioc_id} - {ioc['type']}")

    def add_scan_result(self, scan_data: Dict[str, Any]):
        """Add security scan results to history"""
        scan_result = {
            "id": scan_data.get("id", f"scan_{datetime.utcnow().timestamp()}"),
            "scan_type": scan_data.get("scan_type", "unknown"),
            "target": scan_data.get("target", ""),
            "start_time": scan_data.get("start_time", datetime.utcnow()),
            "end_time": scan_data.get("end_time", datetime.utcnow()),
            "results": scan_data.get("results", {}),
            "vulnerabilities_found": scan_data.get("vulnerabilities_found", []),
            "status": scan_data.get("status", "completed"),
            "tool_used": scan_data.get("tool_used", ""),
            "raw_output": scan_data.get("raw_output", "")
        }

        self.scan_history.append(scan_result)

        # Add vulnerabilities to database if found
        for vuln in scan_result["vulnerabilities_found"]:
            self.add_vulnerability(vuln)

        logger.info(f"Added scan result: {scan_result['id']}")

    def add_incident(self, incident_data: Dict[str, Any]):
        """Add security incident to history"""
        incident = {
            "id": incident_data.get("id", f"incident_{datetime.utcnow().timestamp()}"),
            "title": incident_data.get("title", "Security Incident"),
            "description": incident_data.get("description", ""),
            "severity": incident_data.get("severity", "medium"),
            "status": incident_data.get("status", "open"),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "assigned_agent": incident_data.get("assigned_agent", self.agent_id),
            "affected_systems": incident_data.get("affected_systems", []),
            "indicators": incident_data.get("indicators", []),
            "timeline": incident_data.get("timeline", []),
            "response_actions": incident_data.get("response_actions", []),
            "lessons_learned": incident_data.get("lessons_learned", "")
        }

        self.incident_history.append(incident)
        logger.warning(f"Added security incident: {incident['id']}")

    def add_remediation_action(self, action_data: Dict[str, Any]):
        """Add remediation action"""
        action = {
            "id": action_data.get("id", f"action_{datetime.utcnow().timestamp()}"),
            "vulnerability_id": action_data.get("vulnerability_id"),
            "incident_id": action_data.get("incident_id"),
            "action_type": action_data.get("action_type", "manual"),
            "description": action_data.get("description", ""),
            "status": action_data.get("status", "pending"),
            "priority": action_data.get("priority", "medium"),
            "assigned_to": action_data.get("assigned_to", ""),
            "created_at": datetime.utcnow(),
            "due_date": action_data.get("due_date"),
            "completed_at": action_data.get("completed_at"),
            "result": action_data.get("result", "")
        }

        self.remediation_actions.append(action)
        logger.info(f"Added remediation action: {action['id']}")

    def query_threat_intelligence(self, intel_type: str, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Query threat intelligence with filters"""
        if intel_type not in self.threat_intelligence:
            return []

        intel_items = self.threat_intelligence[intel_type]

        if not filters:
            return intel_items

        # Apply filters
        filtered_items = intel_items.copy()

        if "min_confidence" in filters:
            filtered_items = [item for item in filtered_items
                            if item.get("confidence", 0) >= filters["min_confidence"]]

        if "source" in filters:
            filtered_items = [item for item in filtered_items
                            if item.get("source") == filters["source"]]

        if "tags" in filters:
            filter_tags = filters["tags"]
            filtered_items = [item for item in filtered_items
                            if any(tag in item.get("tags", []) for tag in filter_tags)]

        return filtered_items

    def query_vulnerabilities(self, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Query vulnerabilities with filters"""
        vulns = list(self.vulnerability_database.values())

        if not filters:
            return vulns

        # Apply filters
        if "severity" in filters:
            vulns = [v for v in vulns if v.get("severity") == filters["severity"]]

        if "status" in filters:
            vulns = [v for v in vulns if v.get("status") == filters["status"]]

        if "cve_id" in filters:
            vulns = [v for v in vulns if v.get("cve_id") == filters["cve_id"]]

        if "min_cvss" in filters:
            vulns = [v for v in vulns if v.get("cvss_score", 0) >= filters["min_cvss"]]

        return vulns

    def query_iocs(self, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Query IOCs with filters"""
        iocs = list(self.ioc_database.values())

        if not filters:
            return iocs

        # Apply filters
        if "type" in filters:
            iocs = [i for i in iocs if i.get("type") == filters["type"]]

        if "value" in filters:
            iocs = [i for i in iocs if filters["value"] in i.get("value", "")]

        if "min_confidence" in filters:
            iocs = [i for i in iocs if i.get("confidence", 0) >= filters["min_confidence"]]

        if "severity" in filters:
            iocs = [i for i in iocs if i.get("severity") == filters["severity"]]

        return iocs

    def query_scan_history(self, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Query scan history with filters"""
        scans = self.scan_history.copy()

        if not filters:
            return scans

        # Apply filters
        if "scan_type" in filters:
            scans = [s for s in scans if s.get("scan_type") == filters["scan_type"]]

        if "target" in filters:
            scans = [s for s in scans if filters["target"] in s.get("target", "")]

        if "tool_used" in filters:
            scans = [s for s in scans if s.get("tool_used") == filters["tool_used"]]

        if "status" in filters:
            scans = [s for s in scans if s.get("status") == filters["status"]]

        return scans

    def get_recent_threats(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent threat indicators within specified hours"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        recent_threats = []

        for intel_type, items in self.threat_intelligence.items():
            for item in items:
                if item.get("added_at", datetime.min) > cutoff_time:
                    recent_threats.append({
                        "type": intel_type,
                        "data": item
                    })

        return recent_threats

    def get_security_summary(self) -> Dict[str, Any]:
        """Get comprehensive security summary"""
        summary = {
            "active_vulnerabilities": len([v for v in self.vulnerability_database.values()
                                         if v.get("status") == "open"]),
            "critical_vulnerabilities": len([v for v in self.vulnerability_database.values()
                                           if v.get("severity") == "critical"]),
            "high_confidence_iocs": len([i for i in self.ioc_database.values()
                                       if i.get("confidence", 0) > 0.8]),
            "recent_scans": len([s for s in self.scan_history
                               if s.get("start_time", datetime.min) >
                               datetime.utcnow() - timedelta(days=7)]),
            "open_incidents": len([i for i in self.incident_history
                                 if i.get("status") == "open"]),
            "pending_remediations": len([a for a in self.remediation_actions
                                       if a.get("status") == "pending"]),
            "threat_intel_summary": {
                intel_type: len(items) for intel_type, items in self.threat_intelligence.items()
            }
        }

        return summary

    def correlate_threats(self, target_ioc: str) -> List[Dict[str, Any]]:
        """Correlate threats related to a specific IOC"""
        correlations = []

        # Find related IOCs
        for ioc_id, ioc in self.ioc_database.items():
            if target_ioc in ioc.get("value", "") or target_ioc in ioc.get("related_threats", []):
                correlations.append({
                    "type": "ioc",
                    "data": ioc,
                    "correlation_strength": 0.8
                })

        # Find related vulnerabilities
        for vuln_id, vuln in self.vulnerability_database.items():
            if target_ioc in str(vuln):
                correlations.append({
                    "type": "vulnerability",
                    "data": vuln,
                    "correlation_strength": 0.6
                })

        # Find related incidents
        for incident in self.incident_history:
            if target_ioc in str(incident.get("indicators", [])):
                correlations.append({
                    "type": "incident",
                    "data": incident,
                    "correlation_strength": 0.9
                })

        return correlations
