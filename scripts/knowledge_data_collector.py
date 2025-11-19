"""
Knowledge Base Data Collector
Automated collection of security intelligence data from:
- NVD (National Vulnerability Database)
- OWASP
- CWE (Common Weakness Enumeration)
- Exploit databases
"""
import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
from pathlib import Path
import xml.etree.ElementTree as ET

from sqlalchemy.orm import Session
from data.database import postgres_db
from data.database.models import (
    CVSSScore, CWE, OWASPMapping,
    ExploitIntelligence, ComplianceStandard
)
from common.logger import logger


class KnowledgeDataCollector:
    """Collect and update security knowledge base"""

    def __init__(self, db_session: Session):
        self.session = db_session
        self.nvd_api_key = None  # Optional: get from env
        self.data_dir = Path("data/knowledge_cache")
        self.data_dir.mkdir(parents=True, exist_ok=True)

    async def collect_all(self):
        """Collect all knowledge base data"""
        logger.info("Starting knowledge base data collection...")

        tasks = [
            self.collect_nvd_cves(),
            self.collect_cwe_data(),
            self.collect_owasp_mappings(),
            self.collect_exploit_db(),
        ]

        await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("Knowledge base data collection completed!")

    # ==========================================================================
    # NVD CVE COLLECTION
    # ==========================================================================

    async def collect_nvd_cves(self, days_back: int = 30):
        """
        Collect recent CVEs from National Vulnerability Database

        API: https://services.nvd.nist.gov/rest/json/cves/2.0
        """
        logger.info(f"Collecting NVD CVEs from last {days_back} days...")

        start_date = datetime.now() - timedelta(days=days_back)
        end_date = datetime.now()

        url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
        params = {
            "pubStartDate": start_date.strftime("%Y-%m-%dT00:00:00.000"),
            "pubEndDate": end_date.strftime("%Y-%m-%dT23:59:59.999"),
            "resultsPerPage": 100
        }

        headers = {}
        if self.nvd_api_key:
            headers["apiKey"] = self.nvd_api_key

        try:
            async with aiohttp.ClientSession() as session:
                total_collected = 0
                start_index = 0

                while True:
                    params["startIndex"] = start_index

                    async with session.get(url, params=params, headers=headers) as resp:
                        if resp.status != 200:
                            logger.error(f"NVD API error: {resp.status}")
                            break

                        data = await resp.json()

                        vulnerabilities = data.get("vulnerabilities", [])
                        if not vulnerabilities:
                            break

                        # Process CVEs
                        for vuln_data in vulnerabilities:
                            cve = vuln_data.get("cve", {})
                            self._process_cve(cve)

                        total_collected += len(vulnerabilities)
                        start_index += len(vulnerabilities)

                        # Check if more results
                        total_results = data.get("totalResults", 0)
                        if start_index >= total_results:
                            break

                        # Rate limiting (without API key: 5 requests per 30 seconds)
                        if not self.nvd_api_key:
                            await asyncio.sleep(6)

                self.session.commit()
                logger.info(f"Collected {total_collected} CVEs from NVD")

        except Exception as e:
            logger.error(f"Error collecting NVD CVEs: {e}", exc_info=True)
            self.session.rollback()

    def _process_cve(self, cve_data: Dict):
        """Process and store a single CVE"""
        try:
            cve_id = cve_data.get("id")
            if not cve_id:
                return

            # Extract CVSS scores
            metrics = cve_data.get("metrics", {})

            # CVSS v3.1
            cvss_v31 = metrics.get("cvssMetricV31", [])
            if cvss_v31:
                cvss_data = cvss_v31[0].get("cvssData", {})

                cvss_score = CVSSScore(
                    cve_id=cve_id,
                    version="3.1",
                    base_score=cvss_data.get("baseScore", 0.0),
                    vector_string=cvss_data.get("vectorString", ""),
                    attack_vector=cvss_data.get("attackVector", ""),
                    attack_complexity=cvss_data.get("attackComplexity", ""),
                    privileges_required=cvss_data.get("privilegesRequired", ""),
                    user_interaction=cvss_data.get("userInteraction", ""),
                    scope=cvss_data.get("scope", ""),
                    confidentiality_impact=cvss_data.get("confidentialityImpact", ""),
                    integrity_impact=cvss_data.get("integrityImpact", ""),
                    availability_impact=cvss_data.get("availabilityImpact", ""),
                    exploitability_score=cvss_v31[0].get("exploitabilityScore", 0.0),
                    impact_score=cvss_v31[0].get("impactScore", 0.0)
                )

                # Check if exists
                existing = self.session.query(CVSSScore).filter_by(
                    cve_id=cve_id,
                    version="3.1"
                ).first()

                if not existing:
                    self.session.add(cvss_score)
                    logger.debug(f"Added CVSS score for {cve_id}")

        except Exception as e:
            logger.error(f"Error processing CVE {cve_data.get('id')}: {e}")

    # ==========================================================================
    # CWE DATA COLLECTION
    # ==========================================================================

    async def collect_cwe_data(self):
        """
        Collect CWE data from MITRE

        Source: https://cwe.mitre.org/data/xml/cwec_latest.xml.zip
        """
        logger.info("Collecting CWE data from MITRE...")

        # For this example, we'll use a static dataset
        # In production, download and parse the XML file

        cwe_data = [
            {
                "cwe_id": "CWE-79",
                "name": "Cross-site Scripting (XSS)",
                "description": "The software does not neutralize or incorrectly neutralizes user-controllable input before it is placed in output that is used as a web page that is served to other users.",
                "extended_description": "Cross-site scripting (XSS) vulnerabilities occur when: 1) Data enters a Web application through an untrusted source...",
                "likelihood": "High",
                "severity": "Medium",
                "potential_mitigations": [
                    "Use a vetted library or framework that does not allow this weakness to occur",
                    "Understand the context in which your data will be used",
                    "Use output encoding when generating output",
                    "Implement input validation on all untrusted data"
                ],
                "applicable_platforms": ["Web", "JavaScript", "PHP", "ASP.NET"],
                "common_consequences": [
                    "Execute unauthorized code or commands",
                    "Bypass protection mechanism",
                    "Gain privileges or assume identity"
                ]
            },
            {
                "cwe_id": "CWE-89",
                "name": "SQL Injection",
                "description": "The software constructs all or part of an SQL command using externally-influenced input from an upstream component, but it does not neutralize or incorrectly neutralizes special elements.",
                "extended_description": "Without sufficient removal or quoting of SQL syntax in user-controllable inputs, the generated SQL query can cause those inputs to be interpreted as SQL instead of ordinary user data.",
                "likelihood": "High",
                "severity": "High",
                "potential_mitigations": [
                    "Use parameterized queries (prepared statements)",
                    "Use stored procedures",
                    "Escape all user-supplied input",
                    "Enforce least privilege on database accounts",
                    "Use ORM frameworks properly"
                ],
                "applicable_platforms": ["Database", "SQL", "Web"],
                "common_consequences": [
                    "Execute unauthorized code or commands",
                    "Read application data",
                    "Modify application data",
                    "Bypass protection mechanism"
                ]
            },
            {
                "cwe_id": "CWE-787",
                "name": "Out-of-bounds Write",
                "description": "The software writes data past the end, or before the beginning, of the intended buffer.",
                "extended_description": "Typically, this can result in corruption of data, a crash, or code execution. The software may modify an index or perform pointer arithmetic that references a memory location outside of the boundaries of the buffer.",
                "likelihood": "High",
                "severity": "High",
                "potential_mitigations": [
                    "Use languages that provide automatic bounds checking",
                    "Use a vetted library or framework",
                    "Implement proper input validation",
                    "Use compiler-based canaries",
                    "Use Address Space Layout Randomization (ASLR)"
                ],
                "applicable_platforms": ["C", "C++", "Assembly"],
                "common_consequences": [
                    "Execute unauthorized code or commands",
                    "Modify memory",
                    "DoS: crash or exit"
                ]
            },
            {
                "cwe_id": "CWE-20",
                "name": "Improper Input Validation",
                "description": "The product receives input or data, but it does not validate or incorrectly validates that the input has the properties that are required to process the data safely and correctly.",
                "extended_description": "Input validation is a frequently-used technique for checking potentially dangerous inputs in order to ensure that the inputs are safe for processing within the code.",
                "likelihood": "High",
                "severity": "High",
                "potential_mitigations": [
                    "Assume all input is malicious",
                    "Use an 'accept known good' input validation strategy",
                    "Implement both client-side and server-side validation",
                    "Use strict whitelists",
                    "Decode and canonicalize before validation"
                ],
                "applicable_platforms": ["Any"],
                "common_consequences": [
                    "Varies depending on context",
                    "Code execution",
                    "Data corruption",
                    "Information disclosure"
                ]
            },
            {
                "cwe_id": "CWE-78",
                "name": "OS Command Injection",
                "description": "The software constructs all or part of an OS command using externally-influenced input from an upstream component, but it does not neutralize or incorrectly neutralizes special elements that could modify the intended OS command.",
                "extended_description": "This weakness can lead to a vulnerability in environments in which the attacker does not have direct access to the operating system.",
                "likelihood": "High",
                "severity": "High",
                "potential_mitigations": [
                    "Avoid calling OS commands directly",
                    "Use library calls instead of external processes",
                    "Implement strict input validation",
                    "Use safe APIs that cannot be subverted",
                    "Run with least privilege"
                ],
                "applicable_platforms": ["Any with OS command execution"],
                "common_consequences": [
                    "Execute unauthorized code or commands",
                    "Modify files or directories",
                    "Read application data",
                    "DoS: resource consumption"
                ]
            },
            {
                "cwe_id": "CWE-416",
                "name": "Use After Free",
                "description": "Referencing memory after it has been freed can cause a program to crash, use unexpected values, or execute code.",
                "extended_description": "The use of previously-freed memory can have any number of adverse consequences, ranging from the corruption of valid data to the execution of arbitrary code.",
                "likelihood": "Medium",
                "severity": "High",
                "potential_mitigations": [
                    "Choose languages with automatic memory management",
                    "Use static analysis tools",
                    "Set pointers to NULL after freeing",
                    "Use memory-safe alternatives",
                    "Implement defensive programming"
                ],
                "applicable_platforms": ["C", "C++"],
                "common_consequences": [
                    "Execute unauthorized code",
                    "Modify memory",
                    "DoS: crash"
                ]
            },
            {
                "cwe_id": "CWE-22",
                "name": "Path Traversal",
                "description": "The software uses external input to construct a pathname that is intended to identify a file or directory located underneath a restricted parent directory, but does not properly neutralize special elements.",
                "extended_description": "This allows attackers to traverse the file system to access files or directories that are outside of the restricted directory.",
                "likelihood": "High",
                "severity": "High",
                "potential_mitigations": [
                    "Use indirect reference maps",
                    "Implement strict input validation",
                    "Use chroot jails or sandboxes",
                    "Canonicalize paths before validation",
                    "Use whitelists of allowed files"
                ],
                "applicable_platforms": ["Any with file system access"],
                "common_consequences": [
                    "Read files outside restricted directory",
                    "Modify files",
                    "Execute unauthorized code"
                ]
            },
            {
                "cwe_id": "CWE-352",
                "name": "Cross-Site Request Forgery (CSRF)",
                "description": "The web application does not, or can not, sufficiently verify whether a well-formed, valid, consistent request was intentionally provided by the user who submitted the request.",
                "extended_description": "When a web server is designed to receive a request from a client without any mechanism for verifying that it was intentionally sent, then it might be possible for an attacker to trick a client into making an unintentional request.",
                "likelihood": "Medium",
                "severity": "Medium",
                "potential_mitigations": [
                    "Use anti-CSRF tokens",
                    "Implement SameSite cookie attribute",
                    "Check Referer header",
                    "Use custom headers for AJAX requests",
                    "Re-authenticate for sensitive operations"
                ],
                "applicable_platforms": ["Web"],
                "common_consequences": [
                    "Execute unauthorized functionality",
                    "Modify application data",
                    "Gain privileges"
                ]
            },
            {
                "cwe_id": "CWE-434",
                "name": "Unrestricted Upload of File with Dangerous Type",
                "description": "The software allows the attacker to upload or transfer files of dangerous types that can be automatically processed within the product's environment.",
                "extended_description": "The consequences of unrestricted file upload can vary, including complete system takeover, an overloaded file system or database, forwarding attacks to back-end systems.",
                "likelihood": "Medium",
                "severity": "High",
                "potential_mitigations": [
                    "Validate file type by checking magic numbers",
                    "Use whitelist of allowed extensions",
                    "Store uploads outside web root",
                    "Implement virus scanning",
                    "Use random filenames"
                ],
                "applicable_platforms": ["Web"],
                "common_consequences": [
                    "Execute unauthorized code",
                    "DoS: disk consumption",
                    "Modify files"
                ]
            },
            {
                "cwe_id": "CWE-94",
                "name": "Code Injection",
                "description": "The software constructs all or part of a code segment using externally-influenced input from an upstream component, but it does not neutralize or incorrectly neutralizes special elements.",
                "extended_description": "Code injection differs from command injection in that an attacker is injecting code that is interpreted within the application's own language, not an external OS command.",
                "likelihood": "Medium",
                "severity": "High",
                "potential_mitigations": [
                    "Avoid eval() and similar functions",
                    "Use safe alternatives",
                    "Implement strict input validation",
                    "Use sandboxing",
                    "Apply least privilege"
                ],
                "applicable_platforms": ["PHP", "Python", "JavaScript", "Ruby"],
                "common_consequences": [
                    "Execute unauthorized code",
                    "Modify application logic",
                    "Bypass protection mechanisms"
                ]
            }
        ]

        try:
            for cwe_info in cwe_data:
                # Check if exists
                existing = self.session.query(CWE).filter_by(
                    cwe_id=cwe_info["cwe_id"]
                ).first()

                if not existing:
                    cwe = CWE(
                        cwe_id=cwe_info["cwe_id"],
                        name=cwe_info["name"],
                        description=cwe_info["description"],
                        extended_description=cwe_info.get("extended_description"),
                        likelihood=cwe_info.get("likelihood"),
                        severity=cwe_info.get("severity"),
                        potential_mitigations=json.dumps(cwe_info.get("potential_mitigations", [])),
                        applicable_platforms=json.dumps(cwe_info.get("applicable_platforms", [])),
                        common_consequences=json.dumps(cwe_info.get("common_consequences", []))
                    )
                    self.session.add(cwe)

            self.session.commit()
            logger.info(f"Collected {len(cwe_data)} CWE entries")

        except Exception as e:
            logger.error(f"Error collecting CWE data: {e}", exc_info=True)
            self.session.rollback()

    # ==========================================================================
    # OWASP MAPPINGS
    # ==========================================================================

    async def collect_owasp_mappings(self):
        """Collect OWASP Top 10 to CWE mappings"""
        logger.info("Collecting OWASP mappings...")

        mappings = [
            # A01:2021 - Broken Access Control
            {"cwe_id": "CWE-22", "owasp_category": "A01:2021", "owasp_name": "Broken Access Control", "severity": "High"},
            {"cwe_id": "CWE-23", "owasp_category": "A01:2021", "owasp_name": "Broken Access Control", "severity": "High"},
            {"cwe_id": "CWE-35", "owasp_category": "A01:2021", "owasp_name": "Broken Access Control", "severity": "High"},
            {"cwe_id": "CWE-59", "owasp_category": "A01:2021", "owasp_name": "Broken Access Control", "severity": "High"},
            {"cwe_id": "CWE-200", "owasp_category": "A01:2021", "owasp_name": "Broken Access Control", "severity": "Medium"},
            {"cwe_id": "CWE-284", "owasp_category": "A01:2021", "owasp_name": "Broken Access Control", "severity": "High"},
            {"cwe_id": "CWE-285", "owasp_category": "A01:2021", "owasp_name": "Broken Access Control", "severity": "High"},
            {"cwe_id": "CWE-352", "owasp_category": "A01:2021", "owasp_name": "Broken Access Control", "severity": "Medium"},
            {"cwe_id": "CWE-425", "owasp_category": "A01:2021", "owasp_name": "Broken Access Control", "severity": "Medium"},
            {"cwe_id": "CWE-862", "owasp_category": "A01:2021", "owasp_name": "Broken Access Control", "severity": "High"},

            # A02:2021 - Cryptographic Failures
            {"cwe_id": "CWE-259", "owasp_category": "A02:2021", "owasp_name": "Cryptographic Failures", "severity": "High"},
            {"cwe_id": "CWE-327", "owasp_category": "A02:2021", "owasp_name": "Cryptographic Failures", "severity": "High"},
            {"cwe_id": "CWE-328", "owasp_category": "A02:2021", "owasp_name": "Cryptographic Failures", "severity": "High"},

            # A03:2021 - Injection
            {"cwe_id": "CWE-20", "owasp_category": "A03:2021", "owasp_name": "Injection", "severity": "High"},
            {"cwe_id": "CWE-74", "owasp_category": "A03:2021", "owasp_name": "Injection", "severity": "High"},
            {"cwe_id": "CWE-77", "owasp_category": "A03:2021", "owasp_name": "Injection", "severity": "High"},
            {"cwe_id": "CWE-78", "owasp_category": "A03:2021", "owasp_name": "Injection", "severity": "Critical"},
            {"cwe_id": "CWE-79", "owasp_category": "A03:2021", "owasp_name": "Injection", "severity": "Medium"},
            {"cwe_id": "CWE-88", "owasp_category": "A03:2021", "owasp_name": "Injection", "severity": "High"},
            {"cwe_id": "CWE-89", "owasp_category": "A03:2021", "owasp_name": "Injection", "severity": "Critical"},
            {"cwe_id": "CWE-90", "owasp_category": "A03:2021", "owasp_name": "Injection", "severity": "High"},
            {"cwe_id": "CWE-91", "owasp_category": "A03:2021", "owasp_name": "Injection", "severity": "Medium"},
            {"cwe_id": "CWE-94", "owasp_category": "A03:2021", "owasp_name": "Injection", "severity": "High"},

            # A04:2021 - Insecure Design
            {"cwe_id": "CWE-209", "owasp_category": "A04:2021", "owasp_name": "Insecure Design", "severity": "Low"},
            {"cwe_id": "CWE-256", "owasp_category": "A04:2021", "owasp_name": "Insecure Design", "severity": "Medium"},
            {"cwe_id": "CWE-501", "owasp_category": "A04:2021", "owasp_name": "Insecure Design", "severity": "Medium"},
            {"cwe_id": "CWE-522", "owasp_category": "A04:2021", "owasp_name": "Insecure Design", "severity": "High"},

            # A05:2021 - Security Misconfiguration
            {"cwe_id": "CWE-16", "owasp_category": "A05:2021", "owasp_name": "Security Misconfiguration", "severity": "Medium"},
            {"cwe_id": "CWE-260", "owasp_category": "A05:2021", "owasp_name": "Security Misconfiguration", "severity": "High"},
            {"cwe_id": "CWE-319", "owasp_category": "A05:2021", "owasp_name": "Security Misconfiguration", "severity": "High"},

            # A06:2021 - Vulnerable and Outdated Components
            {"cwe_id": "CWE-1104", "owasp_category": "A06:2021", "owasp_name": "Vulnerable and Outdated Components", "severity": "High"},

            # A07:2021 - Identification and Authentication Failures
            {"cwe_id": "CWE-287", "owasp_category": "A07:2021", "owasp_name": "Identification and Authentication Failures", "severity": "High"},
            {"cwe_id": "CWE-288", "owasp_category": "A07:2021", "owasp_name": "Identification and Authentication Failures", "severity": "High"},
            {"cwe_id": "CWE-290", "owasp_category": "A07:2021", "owasp_name": "Identification and Authentication Failures", "severity": "High"},

            # A08:2021 - Software and Data Integrity Failures
            {"cwe_id": "CWE-345", "owasp_category": "A08:2021", "owasp_name": "Software and Data Integrity Failures", "severity": "High"},
            {"cwe_id": "CWE-353", "owasp_category": "A08:2021", "owasp_name": "Software and Data Integrity Failures", "severity": "Medium"},
            {"cwe_id": "CWE-426", "owasp_category": "A08:2021", "owasp_name": "Software and Data Integrity Failures", "severity": "High"},
            {"cwe_id": "CWE-494", "owasp_category": "A08:2021", "owasp_name": "Software and Data Integrity Failures", "severity": "High"},

            # A09:2021 - Security Logging and Monitoring Failures
            {"cwe_id": "CWE-117", "owasp_category": "A09:2021", "owasp_name": "Security Logging and Monitoring Failures", "severity": "Low"},
            {"cwe_id": "CWE-223", "owasp_category": "A09:2021", "owasp_name": "Security Logging and Monitoring Failures", "severity": "Low"},
            {"cwe_id": "CWE-532", "owasp_category": "A09:2021", "owasp_name": "Security Logging and Monitoring Failures", "severity": "Medium"},
            {"cwe_id": "CWE-778", "owasp_category": "A09:2021", "owasp_name": "Security Logging and Monitoring Failures", "severity": "Low"},

            # A10:2021 - Server-Side Request Forgery (SSRF)
            {"cwe_id": "CWE-918", "owasp_category": "A10:2021", "owasp_name": "Server-Side Request Forgery", "severity": "High"},
        ]

        try:
            for mapping_data in mappings:
                # Check if exists
                existing = self.session.query(OWASPMapping).filter_by(
                    cwe_id=mapping_data["cwe_id"],
                    owasp_category=mapping_data["owasp_category"]
                ).first()

                if not existing:
                    mapping = OWASPMapping(
                        cwe_id=mapping_data["cwe_id"],
                        owasp_category=mapping_data["owasp_category"],
                        owasp_name=mapping_data["owasp_name"],
                        owasp_year=2021,
                        severity=mapping_data["severity"],
                        description=f"{mapping_data['cwe_id']} maps to {mapping_data['owasp_category']}"
                    )
                    self.session.add(mapping)

            self.session.commit()
            logger.info(f"Collected {len(mappings)} OWASP mappings")

        except Exception as e:
            logger.error(f"Error collecting OWASP mappings: {e}", exc_info=True)
            self.session.rollback()

    # ==========================================================================
    # EXPLOIT DATABASE
    # ==========================================================================

    async def collect_exploit_db(self):
        """Collect exploit information"""
        logger.info("Collecting exploit intelligence...")

        # This would connect to exploit-db.com API or similar
        # For now, using sample data

        exploits = [
            {
                "cve_id": "CVE-2024-1234",
                "has_public_exploit": True,
                "exploit_maturity": "functional",
                "exploit_source": "exploit-db",
                "exploit_url": "https://www.exploit-db.com/exploits/12345",
                "actively_exploited": False
            }
        ]

        try:
            for exploit_data in exploits:
                existing = self.session.query(ExploitIntelligence).filter_by(
                    cve_id=exploit_data["cve_id"]
                ).first()

                if not existing:
                    exploit = ExploitIntelligence(**exploit_data)
                    self.session.add(exploit)

            self.session.commit()
            logger.info(f"Collected {len(exploits)} exploit records")

        except Exception as e:
            logger.error(f"Error collecting exploit data: {e}", exc_info=True)
            self.session.rollback()


async def main():
    """Main collection function"""
    with postgres_db.get_session() as session:
        collector = KnowledgeDataCollector(session)
        await collector.collect_all()


if __name__ == "__main__":
    asyncio.run(main())
