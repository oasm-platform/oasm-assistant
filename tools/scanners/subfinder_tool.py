from typing import Dict, Any
from tools.common.base import ToolBase
from data.database import pg

"""
Example usage:
graph.add_node("subfinder", subfinder_tool.to_langgraph_node("domain", "subdomains"))
"""
class SubfinderTool(ToolBase):
    name = "subfinder_tool"
    description = "Subfinder tool for finding subdomains"

    def run(self, args: Dict[str, Any]) -> str:
        domain = args.get("domain")
        result = pg.select_one(
            "SELECT * FROM assets WHERE value = :value",
            {"value": domain}
        )
        return self.parse_output(result)

    def parse_output(self, raw_output: Any) -> Any:
        return raw_output or None
