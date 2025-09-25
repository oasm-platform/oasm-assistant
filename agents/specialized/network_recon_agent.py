"""
Network Reconnaissance Agent for OASM security analysis
"""
from typing import Dict, Any, List

from agents.core import BaseAgent, AgentRole, AgentType, AgentCapability
from common.logger import logger
from llms.prompts import SecurityAgentPrompts


class NetworkReconAgent(BaseAgent):

    def __init__(self, **kwargs):
        super().__init__(
            name="NetworkReconAgent",
            role=AgentRole.SECURITY_RESEARCHER,
            agent_type=AgentType.GOAL_BASED,
            capabilities=[
                AgentCapability(
                    name="network_reconnaissance",
                    description="Perform comprehensive network reconnaissance",
                    tools=["nmap", "subfinder", "httpx", "amass"]
                )
            ],
            **kwargs
        )

    def setup_tools(self) -> List[Any]:
        """Setup network reconnaissance tools"""
        return ["nmap", "subfinder", "httpx", "amass", "masscan"]

    def create_prompt_template(self) -> str:
        """Create network reconnaissance prompt template"""
        return SecurityAgentPrompts.get_network_recon_prompt()

    def process_observation(self, observation: Any) -> Dict[str, Any]:
        """Process network reconnaissance observations"""
        return {
            "hosts_discovered": 0,
            "services_found": [],
            "open_ports": [],
            "subdomains": []
        }

    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute network reconnaissance task"""
        try:
            action = task.get("action", "run_security_scan")

            if action == "run_security_scan":
                return self._run_network_recon(task)
            else:
                return {"success": False, "error": f"Unknown action: {action}"}

        except Exception as e:
            logger.error(f"Network recon task failed: {e}")
            return {"success": False, "error": str(e)}

    def _run_network_recon(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Run network reconnaissance"""
        target = task.get("target", "unknown")

        # Simulate network recon
        recon_result = {
            "target": target,
            "hosts_discovered": 5,
            "open_ports": [22, 80, 443],
            "services": ["ssh", "http", "https"],
            "subdomains": [f"www.{target}", f"api.{target}"],
            "technologies": ["nginx", "php"]
        }

        return {
            "success": True,
            "recon_results": recon_result,
            "agent": self.name
        }