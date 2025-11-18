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

**User Question:**
{question}

**Available MCP Tools:**
{tools_description}

**Your Task:**
1. Analyze the user's question carefully
2. Select the MOST appropriate tool from the list above that best matches the question
3. Generate the correct arguments for that tool

**CRITICAL INSTRUCTIONS:**
- You MUST respond with ONLY valid JSON, nothing else
- Do NOT include any explanation, commentary, or markdown formatting
- Do NOT wrap the JSON in code blocks (no ```)
- workspaceId is REQUIRED for all tools: "{workspace_id}"
- Only use tools from the list above
- Choose based on tool description and user question intent

**Required JSON format (respond with this exact structure):**
{{
    "server": "server-name",
    "tool": "tool-name",
    "args": {{"workspaceId": "{workspace_id}"}},
    "reasoning": "brief explanation why you selected this tool"
}}

**Your JSON response:**"""

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

    @staticmethod
    def get_no_data_response_prompt(question: str) -> str:
        """Prompt for generating response when no scan data is available"""
        return f"""You are an expert security analysis assistant specializing in vulnerability assessment and threat intelligence.

**User's Question:**
"{question}"

**Current Situation:**
This workspace currently has no security scan data available. No assets, vulnerabilities, or security metrics have been collected yet.

**Your Task:**
Generate a helpful, professional response that:
1. Directly acknowledges the user's question
2. Clearly explains that no scan data exists in this workspace
3. Guides the user on next steps (running a security scan to collect data)
4. Maintains a friendly, supportive tone without being overly apologetic
5. **IMPORTANT: Respond in the SAME LANGUAGE as the user's question**

**Response Guidelines:**
- Be concise (2-3 sentences maximum)
- Use natural, conversational language
- Avoid technical jargon unless necessary
- Focus on actionable next steps
- **Match the language of the user's question (English, Vietnamese, etc.)**

**Your Response:"""
