"""
Analysis Agent
Comprehensive vulnerability assessment and reporting based on OASM scan results
"""
from typing import Dict, Any, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from agents.core import BaseAgent, AgentRole, AgentType, AgentCapability
from common.logger import logger
from llms.prompts import SecurityAgentPrompts

from data.retrieval import HybridSearchEngine
from tools.mcp_client import MCPManager


class AnalysisAgent(BaseAgent):
    """
    Analysis Agent

    Collect scan results from OASM Core via MCP and generate comprehensive security reports
    """

    def __init__(
        self,
        db_session: Session,
        workspace_id: Optional['UUID'] = None,
        user_id: Optional['UUID'] = None,
        **kwargs
    ):
        """
        Initialize Analysis Agent

        Args:
            db_session: Database session for knowledge repositories
            workspace_id: Workspace ID for MCP integration (optional)
            user_id: User ID for MCP integration (optional)
        """
        super().__init__(
            name="AnalysisAgent",
            role=AgentRole.ANALYSIS_AGENT,
            agent_type=AgentType.GOAL_BASED,
            capabilities=[
                AgentCapability(
                    name="report_generation",
                    description="Generate comprehensive security reports from scan results",
                    tools=["mcp_data_fetch", "markdown_report_generation"]
                )
            ],
            **kwargs
        )

        self.session = db_session

        # MCP integration - create manager internally if workspace/user provided
        if workspace_id and user_id:
            from data.database import postgres_db
            self.mcp_manager = MCPManager(postgres_db, workspace_id, user_id)
            self._mcp_enabled = True
            logger.debug(f"MCP manager created for workspace {workspace_id}")
        else:
            self.mcp_manager = None
            self._mcp_enabled = False


        # Initialize retrieval system for enhanced remediation
        self.retrieval = HybridSearchEngine(
            table_name="security_knowledge",
            vector_weight=0.7,
            keyword_weight=0.3
        )
        logger.info("Retrieval system initialized successfully")

    def setup_tools(self) -> List[Any]:
        return [
            "mcp_data_fetch",
            "markdown_report_generator"
        ]

    def create_prompt_template(self) -> str:
        return SecurityAgentPrompts.get_analysis_prompt()

    def process_observation(self, observation: Any) -> Dict[str, Any]:
        return {
            "analysis_complete": False,
            "vulnerabilities_found": 0
        }

    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute vulnerability analysis task

        Args:
            task: {
                "action": "analyze_vulnerabilities",
                "scan_results": [...],
                "context": VulnerabilityContext,
                "standards": ["OWASP", "PCI-DSS"]
            }
        """
        try:
            action = task.get("action", "analyze_vulnerabilities")

            if action == "analyze_vulnerabilities":
                return self.analyze_vulnerabilities(
                    scan_results=task.get("scan_results", [])
                )
            elif action == "generate_report":
                return self.generate_reports(
                    analysis_results=task.get("analysis_results", {}),
                    report_types=task.get("report_types", ["technical"])
                )
            else:
                return {"success": False, "error": f"Unknown action: {action}"}

        except Exception as e:
            logger.error(f"Vulnerability analysis failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}


    def generate_reports(
        self,
        analysis_results: Dict,
        report_types: List[str] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive reports

        Report types: technical, executive, compliance, action_list
        """
        report_types = report_types or ["technical"]

        reports = {}

        if "technical" in report_types:
            reports["technical"] = self._generate_technical_report(analysis_results)

        if "executive" in report_types:
            reports["executive"] = self._generate_executive_summary(analysis_results)


        if "action_list" in report_types:
            reports["action_list"] = self._generate_action_list(analysis_results)

        return {
            "success": True,
            "reports": reports,
            "generated_at": "2025-10-24"
        }

    def _generate_technical_report(self, results: Dict) -> str:
        """Generate technical report for security team"""
        vulnerabilities = results.get("vulnerabilities", [])
        summary = results.get("summary", {})

        sections = []
        sections.append("# Security Analysis Technical Report\n")
        sections.append(f"**Total Findings:** {summary.get('total_findings', 0)}\n\n")

        # Severity breakdown
        sections.append("## Summary Statistics\n")
        by_severity = summary.get("by_severity", {})
        for severity, count in sorted(by_severity.items()):
            sections.append(f"- **{severity}:** {count} vulnerabilities\n")

        # Critical vulnerabilities
        sections.append("\n## Critical Vulnerabilities\n")
        critical_vulns = [v for v in vulnerabilities if v.get("severity") in ["Critical", "High"]]

        for i, vuln in enumerate(critical_vulns[:10], 1):
            sections.append(f"\n### {i}. {vuln.get('title', 'Unknown')}\n")
            sections.append(f"- **Severity:** {vuln.get('severity', 'N/A')}\n")
            sections.append(f"- **CVE:** {vuln.get('cve_id') or 'N/A'}\n")
            sections.append(f"- **CWE:** {vuln.get('cwe_id') or 'N/A'}\n")
            sections.append(f"- **Affected Asset:** {vuln.get('affected_asset', 'N/A')}\n")

        return "".join(sections)

    def _generate_executive_summary(self, results: Dict) -> str:
        """Generate executive summary for management"""
        summary = results.get("summary", {})

        by_severity = summary.get("by_severity", {})
        report = f"""# Executive Security Summary

## Overview
A comprehensive security assessment has identified **{summary.get('total_findings', 0)} vulnerabilities** across your attack surface.

## Severity Distribution
- **Critical:** {by_severity.get('Critical', 0)} issues requiring immediate attention
- **High:** {by_severity.get('High', 0)} issues requiring prompt remediation
- **Medium:** {by_severity.get('Medium', 0)} issues for planned remediation
- **Low:** {by_severity.get('Low', 0)} issues for future consideration
- **Info:** {by_severity.get('Info', 0)} informational findings

## Recommended Actions
1. **Immediate (24-48h):** Address all Critical vulnerabilities
2. **Short-term (1-2 weeks):** Remediate High priority issues
3. **Medium-term (1 month):** Implement systematic security improvements

## Cost Estimate
- **Estimated Effort:** {summary.get('total_findings', 0) * 4} hours
- **Approximate Cost:** ${summary.get('total_findings', 0) * 500:,}
"""
        return report.strip()


    def _generate_action_list(self, results: Dict) -> str:
        """Generate prioritized action list for developers"""
        # TODO: Prioritized list of fixes with assignees
        return "# Action List\n\n[Prioritized fixes...]"

    def analyze_vulnerabilities(
        self,
        scan_results: List[Dict] = None,
        scan_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate security analysis reports from scan results

        Args:
            scan_results: Optional scan results
            scan_id: Optional scan ID to fetch from OASM Core via MCP
        """

        # Collect data from OASM Core via MCP (if scan_id provided and no scan_results)
        if not scan_results and scan_id and self.has_mcp:
            logger.info(f"Fetching scan results from MCP: scan_id={scan_id}")
            scan_results = self.fetch_scan_results_sync(scan_id=scan_id)

            if not scan_results:
                logger.warning(f"No scan results fetched from MCP for scan_id={scan_id}")

        if not scan_results:
            return {
                "success": False,
                "error": "No scan results provided or fetched from MCP"
            }

        logger.info(f"Starting vulnerability analysis: {len(scan_results)} scan results")

        # Count by severity
        severity_counts = {}
        for vuln in scan_results:
            severity = vuln.get("severity", "Unknown")
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        # Compile results
        analysis_results = {
            "summary": {
                "total_findings": len(scan_results),
                "by_severity": severity_counts
            },
            "vulnerabilities": scan_results
        }

        # Generate markdown reports
        reports = self.generate_reports(
            analysis_results,
            report_types=["technical", "executive", "action_list"]
        )

        return {
            "success": True,
            "analysis": analysis_results,
            "reports": reports,
            "agent": self.name
        }

    @property
    def has_mcp(self) -> bool:
        """Check if MCP is available"""
        return self._mcp_enabled

    async def fetch_scan_results_from_mcp(
        self,
        scan_id: Optional[str] = None,
        tool: str = "all",
        limit: int = 100
    ) -> List[Dict]:
        """
        Fetch scan results from OASM Core via MCP

        Args:
            scan_id: Specific scan ID (optional)
            tool: Filter by tool (nuclei, nessus, all)
            limit: Max results to return

        Returns:
            List of scan results
        """
        if not self._mcp_enabled:
            logger.debug("MCP not enabled, returning empty results")
            return []

        try:
            result = await self.mcp_manager.call_tool(
                server="oasm-core",
                tool="get_scan_results",
                args={
                    "scan_id": scan_id,
                    "tool": tool,
                    "limit": limit
                }
            )

            scan_results = result.get("scan_results", [])
            logger.info(f"Fetched {len(scan_results)} scan results from MCP")

            return scan_results

        except Exception as e:
            logger.error(f"MCP fetch failed: {e}", exc_info=True)
            return []

    def fetch_scan_results_sync(
        self,
        scan_id: Optional[str] = None,
        tool: str = "all",
        limit: int = 100
    ) -> List[Dict]:
        """
        Synchronous wrapper for fetch_scan_results_from_mcp

        Uses asyncio.run() to execute async function
        """
        if not self._mcp_enabled:
            return []

        try:
            import asyncio
            return asyncio.run(
                self.fetch_scan_results_from_mcp(scan_id, tool, limit)
            )
        except Exception as e:
            logger.error(f"Sync MCP fetch failed: {e}")
            return []
