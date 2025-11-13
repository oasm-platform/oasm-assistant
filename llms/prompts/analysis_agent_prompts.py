from typing import List, Dict, Any
import json


class AnalysisAgentPrompts:
    @staticmethod
    def get_base_security_prompt(agent_name: str, role: str, capabilities: List[str] = None) -> str:
        capabilities_text = ", ".join(capabilities) if capabilities else "general security analysis"

        return f"""You are {agent_name}, a specialized AI security agent with the role of {role}.

Your primary responsibilities:
- Threat detection and analysis
- Vulnerability assessment
- Security monitoring and incident response
- Threat intelligence correlation
- Security tool coordination

Current capabilities: {capabilities_text}

Always respond with:
1. Clear, actionable security recommendations
2. Risk assessments with severity levels (low/medium/high/critical)
3. Specific technical details when analyzing threats
4. Confidence levels for your assessments (0.0-1.0)

You have access to security tools and databases. Use your expertise to provide comprehensive security analysis."""


    @staticmethod
    def get_mcp_tool_selection_prompt(question: str, workspace_id: str, tools_description: str) -> str:
        """
        Prompt for LLM to select the best MCP tool for a given question.
        Used in dynamic tool discovery and selection (like ChatGPT/Claude).
        """
        return f"""You are a security analysis assistant with access to MCP (Model Context Protocol) tools.

User Question: {question}

Available MCP Tools:
{tools_description}

Your task:
1. Analyze the user's question
2. Select the MOST appropriate tool from the list above
3. Generate the correct arguments for that tool

Respond in JSON format:
{{
    "server": "server-name",
    "tool": "tool-name",
    "args": {{"workspaceId": "{workspace_id}", ...}},
    "reasoning": "why you selected this tool"
}}

IMPORTANT:
- workspaceId is REQUIRED for all tools: "{workspace_id}"
- Only use tools from the list above
- Choose based on tool description and user question
"""

    @staticmethod
    def format_statistics_report(stats: Dict) -> str:
        """Format security statistics report"""
        if isinstance(stats, list):
            stats = stats[0] if stats else {}

        report = "Security Overview\n\n"
        report += "Assets:\n"
        report += f"- Total Assets: {stats.get('assets', 0)}\n"
        report += f"- Total Targets: {stats.get('targets', 0)}\n"
        report += f"- Technologies: {stats.get('techs', 0)}\n"
        report += f"- Open Ports: {stats.get('ports', 0)}\n\n"

        report += f"Security Score: {stats.get('score', 0):.1f}/10\n\n"

        report += "Vulnerabilities:\n"
        report += f"- Total: {stats.get('vuls', 0)}\n"
        report += f"- Critical: {stats.get('criticalVuls', 0)}\n"
        report += f"- High: {stats.get('highVuls', 0)}\n"
        report += f"- Medium: {stats.get('mediumVuls', 0)}\n"
        report += f"- Low: {stats.get('lowVuls', 0)}\n"
        report += f"- Info: {stats.get('infoVuls', 0)}\n\n"

        report += "Recommendations:\n"
        if stats.get('criticalVuls', 0) > 0:
            report += f"- URGENT: Address {stats.get('criticalVuls', 0)} critical vulnerabilities\n"
        else:
            report += "- No critical vulnerabilities found\n"

        if stats.get('highVuls', 0) > 0:
            report += f"- Fix {stats.get('highVuls', 0)} high-severity issues\n"

        report += "- Maintain regular security scans\n"

        return report

    @staticmethod
    def format_vulnerabilities_report(data: Dict) -> str:
        """Format vulnerability list report"""
        vulns = data.get("data", []) if isinstance(data, dict) else []
        total = data.get("total", len(vulns)) if isinstance(data, dict) else len(vulns)

        if not vulns:
            return "No vulnerabilities found"

        report = f"Vulnerability Report\n\nFound {total} vulnerabilities:\n\n"

        for i, vuln in enumerate(vulns[:10], 1):
            severity = vuln.get('severity', 'unknown').upper()
            name = vuln.get('name', 'Unknown')
            report += f"{i}. {name} (Severity: {severity})\n"

        if total > 10:
            report += f"\n... and {total - 10} more vulnerabilities\n"

        return report

    @staticmethod
    def format_assets_report(data: Dict) -> str:
        """Format assets/targets list report"""
        items = data.get("data", []) if isinstance(data, dict) else []
        total = data.get("total", len(items)) if isinstance(data, dict) else len(items)

        if not items:
            return "No assets found"

        report = f"Assets Report\n\nFound {total} assets:\n\n"

        for i, item in enumerate(items[:15], 1):
            report += f"{i}. {item.get('value', 'Unknown')}\n"

        if total > 15:
            report += f"\n... and {total - 15} more assets\n"

        return report

    @staticmethod
    def format_generic_report(question: str, data: Any) -> str:
        """Generic format for unknown data types"""
        report = "Analysis Results\n\n"
        report += f"Question: {question}\n\n"
        report += "Data from MCP:\n"
        report += json.dumps(data, indent=2)[:500]
        report += "\n\nPlease review the data above for insights.\n"
        return report

    @staticmethod
    def format_tools_for_llm(all_tools: Dict[str, List[Dict]]) -> str:
        """Format tools description for LLM"""
        formatted = []

        for server_name, tools in all_tools.items():
            for tool in tools:
                tool_info = f"""
Server: {server_name}
Tool: {tool['name']}
Description: {tool['description']}
Required Parameters: {json.dumps(tool.get('input_schema', {}).get('required', []))}
"""
                formatted.append(tool_info.strip())

        return "\n---\n".join(formatted)
