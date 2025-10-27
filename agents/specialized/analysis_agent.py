"""
Analysis Agent
Comprehensive vulnerability assessment and reporting based on OASM scan results
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from uuid import UUID
from sqlalchemy.orm import Session

from agents.core import BaseAgent, AgentRole, AgentType, AgentCapability
from common.logger import logger
from llms.prompts import SecurityAgentPrompts
from knowledge.repositories.owasp_mapping_db import OWASPMappingRepository
from knowledge.repositories.cwe_db import CWERepository
from knowledge.repositories.cvss_db import CVSSRepository
from knowledge.repositories.context_factors_db import ContextFactorsRepository
from knowledge.repositories.exploit_intelligence_db import ExploitIntelligenceRepository
from knowledge.repositories.compliance_db import ComplianceRepository
from knowledge.repositories.compliance_benchmarks_db import ComplianceBenchmarksRepository

# RAG/Retrieval System (optional)
try:
    from data.retrieval import HybridSearchEngine
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    HybridSearchEngine = None
    logger.warning("Retrieval system not available")

# MCP Integration (optional)
try:
    from tools.mcp_client import MCPManager
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    MCPManager = None
    logger.warning("MCP not available")


@dataclass
class VulnerabilityContext:
    """Context information for a vulnerability"""
    environment: str = "production"  # production, staging, dev
    data_sensitivity: str = "general"  # payment, pii, general
    exposure: str = "internal"  # public_internet, internal
    asset_criticality: str = "medium"  # critical, high, medium, low
    industry_sector: str = "technology"
    company_size: str = "medium"


@dataclass
class VulnerabilityFinding:
    """Single vulnerability finding"""
    vuln_id: str
    title: str
    description: str
    cve_id: Optional[str] = None
    cwe_id: Optional[str] = None
    severity: str = "Medium"
    cvss_score: float = 0.0
    affected_asset: str = ""
    tool_source: str = ""  # nuclei, nessus, etc.
    raw_data: Dict = None


class AnalysisAgent(BaseAgent):
    """
    Analysis Agent

    Workflow:
    1. Collect scan results from OASM Core (via MCP if available)
    2. Normalize and deduplicate data
    3. Map to security standards (OWASP, CWE, PCI-DSS)
    4. Calculate context-based risk scores
    5. Assess compliance
    6. Generate remediation plans
    7. Create comprehensive reports
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
                    name="vulnerability_assessment",
                    description="Comprehensive vulnerability analysis and risk scoring",
                    tools=["owasp_mapping", "cwe_mapping", "cvss_scoring", "risk_calculation"]
                ),
                AgentCapability(
                    name="compliance_assessment",
                    description="Security compliance checking and gap analysis",
                    tools=["pci_dss_check", "owasp_compliance", "sans_top25"]
                ),
                AgentCapability(
                    name="remediation_planning",
                    description="Generate detailed remediation plans with code examples",
                    tools=["rag_query", "code_generation", "testing_plans"]
                )
            ],
            **kwargs
        )

        self.session = db_session

        # MCP integration - create manager internally if workspace/user provided
        if workspace_id and user_id and MCP_AVAILABLE:
            try:
                from data.database import postgres_db
                self.mcp_manager = MCPManager(postgres_db, workspace_id, user_id)
                self._mcp_enabled = True
                logger.debug(f"MCP manager created for workspace {workspace_id}")
            except Exception as e:
                logger.warning(f"Failed to create MCP manager: {e}")
                self.mcp_manager = None
                self._mcp_enabled = False
        else:
            self.mcp_manager = None
            self._mcp_enabled = False

        # Initialize repositories
        self.owasp_repo = OWASPMappingRepository(db_session)
        self.cwe_repo = CWERepository(db_session)
        self.cvss_repo = CVSSRepository(db_session)
        self.context_repo = ContextFactorsRepository(db_session)
        self.exploit_repo = ExploitIntelligenceRepository(db_session)
        self.compliance_repo = ComplianceRepository(db_session)
        self.benchmark_repo = ComplianceBenchmarksRepository(db_session)

        # Initialize retrieval system for enhanced remediation
        if RAG_AVAILABLE:
            try:
                self.retrieval = HybridSearchEngine(
                    table_name="security_knowledge",
                    vector_weight=0.7,
                    keyword_weight=0.3
                )
                logger.info("Retrieval system initialized successfully")
            except Exception as e:
                logger.warning(f"Retrieval system initialization failed: {e}")
                self.retrieval = None
        else:
            self.retrieval = None

    def setup_tools(self) -> List[Any]:
        return [
            "owasp_mapper",
            "cwe_analyzer",
            "cvss_calculator",
            "risk_scorer",
            "compliance_checker",
            "remediation_generator"
        ]

    def create_prompt_template(self) -> str:
        return SecurityAgentPrompts.get_analysis_prompt()

    def process_observation(self, observation: Any) -> Dict[str, Any]:
        return {
            "analysis_complete": False,
            "vulnerabilities_found": 0,
            "risk_score": 0.0
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
                    scan_results=task.get("scan_results", []),
                    context=task.get("context", VulnerabilityContext()),
                    standards=task.get("standards", ["OWASP"])
                )
            elif action == "calculate_risk_score":
                return self.calculate_risk_score(
                    vulnerability=task.get("vulnerability"),
                    context=task.get("context", VulnerabilityContext())
                )
            elif action == "assess_compliance":
                return self.assess_compliance(
                    vulnerabilities=task.get("vulnerabilities", []),
                    standards=task.get("standards", ["OWASP"])
                )
            elif action == "generate_remediation":
                return self.generate_remediation_plan(
                    vulnerability=task.get("vulnerability")
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

    # ============================================================================
    # STEP 2: NORMALIZE & DEDUPLICATE DATA
    # ============================================================================

    def normalize_scan_results(self, scan_results: List[Dict]) -> List[VulnerabilityFinding]:
        """
        Normalize vulnerability data from different tools

        Supports: Nuclei, Nessus, custom formats
        """
        findings = []

        for result in scan_results:
            tool = result.get("tool", "unknown")

            if tool == "nuclei":
                finding = self._normalize_nuclei(result)
            elif tool == "nessus":
                finding = self._normalize_nessus(result)
            else:
                finding = self._normalize_generic(result)

            if finding:
                findings.append(finding)

        # Deduplicate
        return self._deduplicate_findings(findings)

    def _normalize_nuclei(self, result: Dict) -> VulnerabilityFinding:
        """Normalize Nuclei scan result"""
        return VulnerabilityFinding(
            vuln_id=result.get("template-id", "unknown"),
            title=result.get("info", {}).get("name", "Unknown"),
            description=result.get("info", {}).get("description", ""),
            severity=result.get("info", {}).get("severity", "info").title(),
            cve_id=self._extract_cve(result.get("info", {}).get("tags", [])),
            cwe_id=self._extract_cwe(result.get("info", {}).get("classification", {})),
            affected_asset=result.get("host", ""),
            tool_source="nuclei",
            raw_data=result
        )

    def _normalize_nessus(self, result: Dict) -> VulnerabilityFinding:
        """Normalize Nessus scan result"""
        return VulnerabilityFinding(
            vuln_id=str(result.get("pluginID", "unknown")),
            title=result.get("pluginName", "Unknown"),
            description=result.get("description", ""),
            severity=self._map_nessus_severity(result.get("severity", 0)),
            cve_id=result.get("cve", [None])[0] if result.get("cve") else None,
            cvss_score=result.get("cvss_base_score", 0.0),
            affected_asset=result.get("host-fqdn", ""),
            tool_source="nessus",
            raw_data=result
        )

    def _normalize_generic(self, result: Dict) -> VulnerabilityFinding:
        """Normalize generic scan result"""
        return VulnerabilityFinding(
            vuln_id=result.get("id", "unknown"),
            title=result.get("title", "Unknown"),
            description=result.get("description", ""),
            severity=result.get("severity", "Medium"),
            cve_id=result.get("cve"),
            cwe_id=result.get("cwe"),
            cvss_score=result.get("cvss_score", 0.0),
            affected_asset=result.get("asset", ""),
            tool_source=result.get("tool", "unknown"),
            raw_data=result
        )

    def _deduplicate_findings(self, findings: List[VulnerabilityFinding]) -> List[VulnerabilityFinding]:
        """Remove duplicate findings"""
        seen = set()
        unique_findings = []

        for finding in findings:
            # Create unique key
            key = (
                finding.cve_id or finding.cwe_id or finding.title,
                finding.affected_asset
            )

            if key not in seen:
                seen.add(key)
                unique_findings.append(finding)

        logger.info(f"Deduplicated: {len(findings)} → {len(unique_findings)} findings")
        return unique_findings

    # ============================================================================
    # STEP 3: MAP TO SECURITY STANDARDS
    # ============================================================================

    def map_to_standards(self, finding: VulnerabilityFinding) -> Dict[str, Any]:
        """Map vulnerability to OWASP, CWE, compliance standards"""

        mapping = {
            "owasp": None,
            "cwe": None,
            "compliance": {}
        }

        # OWASP mapping
        owasp_mapping = self.owasp_repo.map_vulnerability_to_owasp(
            cve_id=finding.cve_id,
            cwe_id=finding.cwe_id
        )
        mapping["owasp"] = owasp_mapping

        # CWE details
        if finding.cwe_id:
            cwe = self.cwe_repo.get_by_id(finding.cwe_id)
            if cwe:
                mapping["cwe"] = {
                    "id": cwe.cwe_id,
                    "name": cwe.name,
                    "description": cwe.description,
                    "likelihood": cwe.likelihood
                }

        # Compliance mapping
        compliance_map = self.compliance_repo.map_vulnerability_to_compliance(
            cwe_id=finding.cwe_id,
            owasp_category=owasp_mapping.get("owasp_category") if owasp_mapping else None
        )
        mapping["compliance"] = compliance_map

        return mapping

    # ============================================================================
    # STEP 4: CALCULATE CONTEXT-BASED RISK SCORE
    # ============================================================================

    def calculate_risk_score(
        self,
        vulnerability: VulnerabilityFinding,
        context: VulnerabilityContext
    ) -> Dict[str, Any]:
        """
        Calculate risk score with context factors

        Risk Score = CVSS Base Score × Context Multipliers × Exploit Multiplier
        """

        # Get CVSS base score
        base_score = vulnerability.cvss_score
        if not base_score and vulnerability.cve_id:
            cvss = self.cvss_repo.get_latest_score(vulnerability.cve_id)
            base_score = cvss.base_score if cvss else self._estimate_cvss_from_severity(vulnerability.severity)

        # Calculate context multiplier
        context_multiplier = self.context_repo.calculate_context_multiplier({
            "environment": context.environment,
            "data_sensitivity": context.data_sensitivity,
            "exposure": context.exposure,
            "asset_criticality": context.asset_criticality
        })

        # Calculate exploit multiplier
        exploit_multiplier = 1.0
        if vulnerability.cve_id:
            exploit_multiplier = self.exploit_repo.calculate_exploit_multiplier(vulnerability.cve_id)

        # Final risk score
        risk_score = base_score * context_multiplier * exploit_multiplier
        risk_score = min(risk_score, 10.0)  # Cap at 10.0

        # Assign priority
        priority = self._assign_priority(risk_score)

        return {
            "base_score": base_score,
            "context_multiplier": context_multiplier,
            "exploit_multiplier": exploit_multiplier,
            "final_risk_score": round(risk_score, 2),
            "priority": priority,
            "factors": {
                "environment": context.environment,
                "data_sensitivity": context.data_sensitivity,
                "exposure": context.exposure,
                "asset_criticality": context.asset_criticality,
                "has_exploit": exploit_multiplier > 1.0,
                "actively_exploited": self.exploit_repo.is_actively_exploited(vulnerability.cve_id) if vulnerability.cve_id else False
            }
        }

    def _estimate_cvss_from_severity(self, severity: str) -> float:
        """Estimate CVSS score from severity string"""
        severity_map = {
            "Critical": 9.5,
            "High": 7.5,
            "Medium": 5.0,
            "Low": 3.0,
            "Info": 0.0
        }
        return severity_map.get(severity, 5.0)

    def _assign_priority(self, risk_score: float) -> str:
        """Assign priority based on risk score"""
        if risk_score >= 9.0:
            return "P0"  # Critical
        elif risk_score >= 7.0:
            return "P1"  # High
        elif risk_score >= 4.0:
            return "P2"  # Medium
        else:
            return "P3"  # Low

    # ============================================================================
    # STEP 5: ASSESS COMPLIANCE
    # ============================================================================

    def assess_compliance(
        self,
        vulnerabilities: List[VulnerabilityFinding],
        standards: List[str] = None
    ) -> Dict[str, Any]:
        """
        Assess compliance with security standards

        Returns compliance score, gaps, and recommendations
        """
        standards = standards or ["OWASP", "PCI-DSS"]

        compliance_results = {}

        # Prepare vulnerability data
        vuln_data = [
            {"cwe_id": v.cwe_id, "severity": v.severity}
            for v in vulnerabilities
            if v.cwe_id
        ]

        # Check PCI-DSS
        if "PCI-DSS" in standards:
            pci_result = self.compliance_repo.check_pci_dss_compliance(vuln_data)
            compliance_results["PCI-DSS"] = pci_result

        # Check OWASP compliance
        if "OWASP" in standards:
            owasp_result = self._check_owasp_compliance(vulnerabilities)
            compliance_results["OWASP"] = owasp_result

        return {
            "standards_checked": standards,
            "results": compliance_results,
            "overall_status": self._calculate_overall_compliance(compliance_results)
        }

    def _check_owasp_compliance(self, vulnerabilities: List[VulnerabilityFinding]) -> Dict:
        """Check OWASP Top 10 compliance"""

        # Get category statistics
        category_stats = {}

        for vuln in vulnerabilities:
            mapping = self.owasp_repo.map_vulnerability_to_owasp(
                cve_id=vuln.cve_id,
                cwe_id=vuln.cwe_id
            )

            if mapping:
                category = mapping["owasp_category"]
                if category not in category_stats:
                    category_stats[category] = {
                        "name": mapping["owasp_name"],
                        "count": 0
                    }
                category_stats[category]["count"] += 1

        # Calculate compliance score (100 - percentage of categories with issues)
        total_categories = 10  # OWASP Top 10
        categories_with_issues = len(category_stats)
        compliance_score = max(0, 100 - (categories_with_issues / total_categories * 100))

        return {
            "total_categories": total_categories,
            "categories_with_issues": categories_with_issues,
            "compliance_score": round(compliance_score, 2),
            "category_breakdown": category_stats,
            "status": "PASS" if categories_with_issues == 0 else "FAIL"
        }

    def _calculate_overall_compliance(self, results: Dict) -> str:
        """Calculate overall compliance status"""
        statuses = [r.get("status") for r in results.values()]
        return "PASS" if all(s == "PASS" for s in statuses) else "FAIL"

    # ============================================================================
    # STEP 6: GENERATE REMEDIATION PLANS
    # ============================================================================

    def generate_remediation_plan(self, vulnerability: VulnerabilityFinding) -> Dict[str, Any]:
        """
        Generate 3-phase remediation plan with RAG-enhanced recommendations

        Phase 1: Immediate (2-4h) - Temporary fixes
        Phase 2: Short-term (1-3 days) - Proper fixes
        Phase 3: Long-term (1-2 weeks) - Systematic solutions
        """

        # Get CWE mitigation strategies from database
        mitigations = ""
        if vulnerability.cwe_id:
            mitigations = self.cwe_repo.get_mitigation_strategies(vulnerability.cwe_id)

        # Build base plan
        plan = {
            "vulnerability": {
                "id": vulnerability.vuln_id,
                "title": vulnerability.title,
                "severity": vulnerability.severity
            },
            "phases": {
                "immediate": self._generate_immediate_fix(vulnerability),
                "short_term": self._generate_short_term_fix(vulnerability),
                "long_term": self._generate_long_term_fix(vulnerability, mitigations)
            },
            "effort_estimate": self._estimate_effort(vulnerability),
            "verification": self._generate_verification_checklist(vulnerability)
        }

        # Enhance with retrieval system if available
        if self.retrieval:
            try:
                # TODO: Implement retrieval-based enhancement using HybridSearchEngine
                # Query knowledge base for relevant remediation guidance
                pass
            except Exception as e:
                logger.error(f"Error enhancing with retrieval: {e}", exc_info=True)

        return plan

    def _generate_immediate_fix(self, vuln: VulnerabilityFinding) -> Dict:
        """Generate immediate temporary fix (2-4h)"""
        return {
            "timeline": "2-4 hours",
            "type": "Temporary mitigation",
            "steps": [
                "Review affected asset and verify vulnerability",
                "Apply temporary workaround (e.g., disable feature, add WAF rule)",
                "Monitor for exploitation attempts",
                "Document temporary fix"
            ],
            "examples": []
        }

    def _generate_short_term_fix(self, vuln: VulnerabilityFinding) -> Dict:
        """Generate short-term proper fix (1-3 days)"""
        return {
            "timeline": "1-3 days",
            "type": "Proper fix",
            "steps": [
                "Review code and identify root cause",
                "Implement secure coding fix",
                "Run unit tests and security tests",
                "Deploy to staging environment",
                "Verify fix effectiveness"
            ],
            "code_examples": []
        }

    def _generate_long_term_fix(self, vuln: VulnerabilityFinding, mitigations: str) -> Dict:
        """Generate long-term systematic solution (1-2 weeks)"""
        return {
            "timeline": "1-2 weeks",
            "type": "Systematic solution",
            "steps": [
                "Architect secure solution",
                "Implement security controls (input validation, output encoding, etc.)",
                "Add automated security tests",
                "Update security policies and procedures",
                "Conduct security training for team"
            ],
            "best_practices": mitigations or "See CWE documentation",
            "preventive_measures": []
        }

    def _estimate_effort(self, vuln: VulnerabilityFinding) -> Dict:
        """Estimate remediation effort"""
        severity_effort = {
            "Critical": {"hours": 8, "cost": 1000},
            "High": {"hours": 6, "cost": 750},
            "Medium": {"hours": 4, "cost": 500},
            "Low": {"hours": 2, "cost": 250}
        }

        return severity_effort.get(vuln.severity, {"hours": 4, "cost": 500})

    def _generate_verification_checklist(self, vuln: VulnerabilityFinding) -> List[str]:
        """Generate verification checklist"""
        return [
            "Run original scan tool to confirm fix",
            "Perform manual verification",
            "Run regression tests",
            "Security team review",
            "Update documentation"
        ]

    # ============================================================================
    # STEP 7: GENERATE REPORTS
    # ============================================================================

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

        if "compliance" in report_types:
            reports["compliance"] = self._generate_compliance_report(analysis_results)

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
        compliance = results.get("compliance", {})

        sections = []
        sections.append("# Security Analysis Technical Report\n")
        sections.append(f"**Total Findings:** {summary.get('total_findings', 0)}\n\n")

        # Priority breakdown
        sections.append("## Summary Statistics\n")
        by_priority = summary.get("by_priority", {})
        for priority, count in sorted(by_priority.items()):
            sections.append(f"- **{priority}:** {count} vulnerabilities\n")

        # Critical vulnerabilities
        sections.append("\n## Critical Vulnerabilities\n")
        critical_vulns = [v for v in vulnerabilities if v.get("risk", {}).get("priority") == "P0"]

        for i, vuln_data in enumerate(critical_vulns[:10], 1):
            finding = vuln_data.get("finding")
            risk = vuln_data.get("risk", {})
            mapping = vuln_data.get("mapping", {})

            sections.append(f"\n### {i}. {finding.title}\n")
            sections.append(f"- **CWE:** {finding.cwe_id or 'N/A'}\n")
            sections.append(f"- **Risk Score:** {risk.get('final_risk_score', 0)}\n")
            sections.append(f"- **OWASP:** {mapping.get('owasp', {}).get('owasp_category', 'N/A')}\n")
            sections.append(f"- **Affected Asset:** {finding.affected_asset}\n")

        # Compliance status
        sections.append("\n## Compliance Assessment\n")
        for standard, result in compliance.get("results", {}).items():
            sections.append(f"\n### {standard}\n")
            sections.append(f"- **Status:** {result.get('status', 'UNKNOWN')}\n")
            sections.append(f"- **Score:** {result.get('compliance_score', 0)}%\n")

        return "".join(sections)

    def _generate_executive_summary(self, results: Dict) -> str:
        """Generate executive summary for management"""
        summary = results.get("summary", {})
        compliance = results.get("compliance", {})

        report = f"""# Executive Security Summary

## Overview
A comprehensive security assessment has identified **{summary.get('total_findings', 0)} vulnerabilities** across your attack surface.

## Risk Distribution
- **Critical (P0):** {summary.get('by_priority', {}).get('P0', 0)} issues requiring immediate attention
- **High (P1):** {summary.get('by_priority', {}).get('P1', 0)} issues requiring prompt remediation
- **Medium (P2):** {summary.get('by_priority', {}).get('P2', 0)} issues for planned remediation
- **Low (P3):** {summary.get('by_priority', {}).get('P3', 0)} issues for future consideration

## Compliance Status
**Overall:** {compliance.get('overall_status', 'UNKNOWN')}

## Recommended Actions
1. **Immediate (24-48h):** Address all P0 critical vulnerabilities
2. **Short-term (1-2 weeks):** Remediate P1 high-priority issues
3. **Medium-term (1 month):** Implement systematic security improvements

## Cost Estimate
- **Estimated Effort:** {summary.get('total_findings', 0) * 4} hours
- **Approximate Cost:** ${summary.get('total_findings', 0) * 500:,}
"""
        return report.strip()

    def _generate_compliance_report(self, results: Dict) -> str:
        """Generate compliance report for auditors"""
        # TODO: Compliance status, gaps, remediation timeline
        return "# Compliance Assessment Report\n\n[Compliance details...]"

    def _generate_action_list(self, results: Dict) -> str:
        """Generate prioritized action list for developers"""
        # TODO: Prioritized list of fixes with assignees
        return "# Action List\n\n[Prioritized fixes...]"

    # ============================================================================
    # MAIN ANALYSIS WORKFLOW
    # ============================================================================

    def analyze_vulnerabilities(
        self,
        scan_results: List[Dict] = None,
        scan_id: Optional[str] = None,
        context: VulnerabilityContext = None,
        standards: List[str] = None
    ) -> Dict[str, Any]:
        """
        Complete vulnerability analysis workflow

        Executes all 7 steps:
        1. Collect data (from scan_results OR fetch via MCP using scan_id)
        2. Normalize & deduplicate
        3. Map to standards
        4. Calculate risk scores
        5. Assess compliance
        6. Generate remediation plans
        7. Create reports

        Args:
            scan_results: Optional scan results (existing behavior)
            scan_id: Optional scan ID to fetch from OASM Core via MCP
            context: Vulnerability context information
            standards: Security standards to check compliance
        """
        context = context or VulnerabilityContext()
        standards = standards or ["OWASP", "PCI-DSS"]

        # Step 1: Collect data from OASM Core via MCP (if scan_id provided and no scan_results)
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

        # Step 2: Normalize
        findings = self.normalize_scan_results(scan_results)
        logger.info(f"Normalized to {len(findings)} unique findings")

        # Step 3 & 4: Map and score each finding
        analyzed_vulns = []
        for finding in findings:
            mapping = self.map_to_standards(finding)
            risk_analysis = self.calculate_risk_score(finding, context)

            analyzed_vulns.append({
                "finding": finding,
                "mapping": mapping,
                "risk": risk_analysis
            })

        # Sort by risk score
        analyzed_vulns.sort(key=lambda x: x["risk"]["final_risk_score"], reverse=True)

        # Step 5: Compliance assessment
        compliance_assessment = self.assess_compliance(findings, standards)

        # Step 6: Generate remediation plans (top 10 critical)
        remediation_plans = []
        for vuln_data in analyzed_vulns[:10]:
            plan = self.generate_remediation_plan(vuln_data["finding"])
            remediation_plans.append(plan)

        # Compile results
        analysis_results = {
            "summary": {
                "total_findings": len(findings),
                "by_priority": self._count_by_priority(analyzed_vulns),
                "by_severity": self._count_by_severity(findings),
                "highest_risk_score": analyzed_vulns[0]["risk"]["final_risk_score"] if analyzed_vulns else 0
            },
            "vulnerabilities": analyzed_vulns,
            "compliance": compliance_assessment,
            "remediation_plans": remediation_plans,
            "context": context
        }

        # Step 7: Generate reports
        reports = self.generate_reports(
            analysis_results,
            report_types=["technical", "executive", "compliance", "action_list"]
        )

        return {
            "success": True,
            "analysis": analysis_results,
            "reports": reports,
            "agent": self.name
        }

    def _count_by_priority(self, analyzed_vulns: List[Dict]) -> Dict[str, int]:
        """Count vulnerabilities by priority"""
        counts = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
        for vuln in analyzed_vulns:
            priority = vuln["risk"]["priority"]
            counts[priority] = counts.get(priority, 0) + 1
        return counts

    def _count_by_severity(self, findings: List[VulnerabilityFinding]) -> Dict[str, int]:
        """Count findings by severity"""
        counts = {}
        for finding in findings:
            counts[finding.severity] = counts.get(finding.severity, 0) + 1
        return counts

    # ==========================================================================
    # RAG INTEGRATION HELPERS
    # ==========================================================================

    # def _get_rag_remediation(self, vuln: VulnerabilityFinding) -> Dict[str, Any]:
    #     """
    #     Query retrieval system for remediation details
    #     TODO: Implement using HybridSearchEngine from data.retrieval
    #     """
    #     if not self.retrieval:
    #         return {}
    #
    #     # TODO: Query security knowledge base using hybrid search
    #     # Example:
    #     # results = self.retrieval.search(
    #     #     query=f"{vuln.title} {vuln.cwe_id} remediation",
    #     #     k=5
    #     # )
    #
    #     return {}

    # Helper methods
    def _extract_cve(self, tags: List[str]) -> Optional[str]:
        """Extract CVE ID from tags"""
        for tag in tags:
            if tag.startswith("cve-"):
                return tag.upper().replace("CVE-", "CVE-")
        return None

    def _extract_cwe(self, classification: Dict) -> Optional[str]:
        """Extract CWE ID from classification"""
        cwe_id = classification.get("cwe-id")
        return f"CWE-{cwe_id}" if cwe_id else None

    def _map_nessus_severity(self, severity_num: int) -> str:
        """Map Nessus severity number to string"""
        severity_map = {
            4: "Critical",
            3: "High",
            2: "Medium",
            1: "Low",
            0: "Info"
        }
        return severity_map.get(severity_num, "Medium")

    # ==========================================================================
    # MCP INTEGRATION HELPERS
    # ==========================================================================

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
            logger.info(f"Fetching scan results via MCP: scan_id={scan_id}, tool={tool}")

            result = await self.mcp_manager.call_tool(
                server_name="oasm-core",
                tool_name="get_scan_results",
                arguments={
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
