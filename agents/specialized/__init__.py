"""
Specialized security agents for OASM Assistant
"""

from .threat_detection_agent import ThreatDetectionAgent
from .vulnerability_scan_agent import VulnerabilityScanAgent
from .network_recon_agent import NetworkReconAgent
from .report_generation_agent import ReportGenerationAgent
from .web_security_agent import WebSecurityAgent
from .nuclei_generation_agent import NucleiGenerationAgent

__all__ = [
    "ThreatDetectionAgent",
    "VulnerabilityScanAgent",
    "NetworkReconAgent",
    "ReportGenerationAgent",
    "WebSecurityAgent",
    "NucleiGenerationAgent",
]