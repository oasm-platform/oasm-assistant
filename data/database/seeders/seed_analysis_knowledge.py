"""
Seed data for Analysis Agent knowledge base
Populates OWASP, CWE, CVSS, Context Factors, etc.
"""
from sqlalchemy.orm import Session
from data.database.models import (
    OWASPMapping, CWE, ComplianceStandard, CVSSScore,
    ContextFactor, ExploitIntelligence, ComplianceBenchmark
)
from common.logger import logger


class AnalysisKnowledgeSeeder:
    """Seed analysis agent knowledge base"""

    def __init__(self, session: Session):
        self.session = session

    def seed_all(self):
        """Seed all knowledge base data"""
        logger.info("Starting knowledge base seeding...")

        self.seed_owasp_mappings()
        self.seed_cwe()
        self.seed_context_factors()
        self.seed_compliance_standards()
        self.seed_compliance_benchmarks()
        self.seed_sample_cvss()
        self.seed_sample_exploits()

        logger.info("Knowledge base seeding completed!")

    # ==========================================================================
    # OWASP MAPPINGS
    # ==========================================================================

    def seed_owasp_mappings(self):
        """Seed OWASP Top 10 2021 mappings"""
        logger.info("Seeding OWASP mappings...")

        mappings = [
            # A01:2021 - Broken Access Control
            {
                "cwe_id": "CWE-22",
                "owasp_category": "A01:2021",
                "owasp_name": "Broken Access Control",
                "owasp_year": 2021,
                "severity": "High",
                "description": "Path Traversal"
            },
            {
                "cwe_id": "CWE-78",
                "owasp_category": "A01:2021",
                "owasp_name": "Broken Access Control",
                "owasp_year": 2021,
                "severity": "Critical",
                "description": "OS Command Injection"
            },
            # A02:2021 - Cryptographic Failures
            {
                "cwe_id": "CWE-327",
                "owasp_category": "A02:2021",
                "owasp_name": "Cryptographic Failures",
                "owasp_year": 2021,
                "severity": "High",
                "description": "Use of Broken Crypto"
            },
            # A03:2021 - Injection
            {
                "cwe_id": "CWE-89",
                "owasp_category": "A03:2021",
                "owasp_name": "Injection",
                "owasp_year": 2021,
                "severity": "Critical",
                "description": "SQL Injection"
            },
            {
                "cwe_id": "CWE-79",
                "owasp_category": "A03:2021",
                "owasp_name": "Injection",
                "owasp_year": 2021,
                "severity": "Medium",
                "description": "Cross-Site Scripting (XSS)"
            },
            {
                "cwe_id": "CWE-77",
                "owasp_category": "A03:2021",
                "owasp_name": "Injection",
                "owasp_year": 2021,
                "severity": "High",
                "description": "Command Injection"
            },
            # A04:2021 - Insecure Design
            {
                "cwe_id": "CWE-209",
                "owasp_category": "A04:2021",
                "owasp_name": "Insecure Design",
                "owasp_year": 2021,
                "severity": "Low",
                "description": "Information Exposure"
            },
            # A05:2021 - Security Misconfiguration
            {
                "cwe_id": "CWE-16",
                "owasp_category": "A05:2021",
                "owasp_name": "Security Misconfiguration",
                "owasp_year": 2021,
                "severity": "Medium",
                "description": "Configuration"
            },
            # A06:2021 - Vulnerable and Outdated Components
            {
                "cwe_id": "CWE-1035",
                "owasp_category": "A06:2021",
                "owasp_name": "Vulnerable and Outdated Components",
                "owasp_year": 2021,
                "severity": "High",
                "description": "Outdated Components"
            },
            # A07:2021 - Identification and Authentication Failures
            {
                "cwe_id": "CWE-287",
                "owasp_category": "A07:2021",
                "owasp_name": "Identification and Authentication Failures",
                "owasp_year": 2021,
                "severity": "Critical",
                "description": "Improper Authentication"
            },
            {
                "cwe_id": "CWE-798",
                "owasp_category": "A07:2021",
                "owasp_name": "Identification and Authentication Failures",
                "owasp_year": 2021,
                "severity": "Critical",
                "description": "Hardcoded Credentials"
            },
            # A08:2021 - Software and Data Integrity Failures
            {
                "cwe_id": "CWE-502",
                "owasp_category": "A08:2021",
                "owasp_name": "Software and Data Integrity Failures",
                "owasp_year": 2021,
                "severity": "Critical",
                "description": "Deserialization of Untrusted Data"
            },
            # A09:2021 - Security Logging and Monitoring Failures
            {
                "cwe_id": "CWE-778",
                "owasp_category": "A09:2021",
                "owasp_name": "Security Logging and Monitoring Failures",
                "owasp_year": 2021,
                "severity": "Medium",
                "description": "Insufficient Logging"
            },
            # A10:2021 - Server-Side Request Forgery (SSRF)
            {
                "cwe_id": "CWE-918",
                "owasp_category": "A10:2021",
                "owasp_name": "Server-Side Request Forgery",
                "owasp_year": 2021,
                "severity": "High",
                "description": "SSRF"
            }
        ]

        for data in mappings:
            mapping = OWASPMapping(**data)
            self.session.add(mapping)

        self.session.commit()
        logger.info(f"Seeded {len(mappings)} OWASP mappings")

    # ==========================================================================
    # CWE DATABASE
    # ==========================================================================

    def seed_cwe(self):
        """Seed common CWEs"""
        logger.info("Seeding CWE database...")

        cwes = [
            {
                "cwe_id": "CWE-89",
                "name": "SQL Injection",
                "description": "The software constructs all or part of an SQL command using externally-influenced input from an upstream component",
                "abstraction": "Base",
                "likelihood": "High",
                "potential_mitigations": "Use parameterized queries (prepared statements). Use ORM frameworks. Implement input validation.",
                "capec_ids": ["CAPEC-66"]
            },
            {
                "cwe_id": "CWE-79",
                "name": "Cross-Site Scripting (XSS)",
                "description": "The software does not neutralize or incorrectly neutralizes user-controllable input before it is placed in output",
                "abstraction": "Base",
                "likelihood": "High",
                "potential_mitigations": "Encode all output. Use Content Security Policy. Implement input validation.",
                "capec_ids": ["CAPEC-18", "CAPEC-86"]
            },
            {
                "cwe_id": "CWE-78",
                "name": "OS Command Injection",
                "description": "The software constructs OS commands using externally-influenced input",
                "abstraction": "Base",
                "likelihood": "High",
                "potential_mitigations": "Avoid system calls. Use parameterized APIs. Implement strict input validation.",
                "capec_ids": ["CAPEC-88"]
            },
            {
                "cwe_id": "CWE-22",
                "name": "Path Traversal",
                "description": "The software uses external input to construct a pathname that should be within a restricted directory, but it does not properly neutralize sequences such as '..'",
                "abstraction": "Base",
                "likelihood": "Medium",
                "potential_mitigations": "Validate all file paths. Use allowlists. Implement chroot jails.",
                "capec_ids": ["CAPEC-126", "CAPEC-64"]
            },
            {
                "cwe_id": "CWE-918",
                "name": "Server-Side Request Forgery (SSRF)",
                "description": "The web server receives a URL or similar request from an upstream component and retrieves the contents of this URL",
                "abstraction": "Base",
                "likelihood": "Medium",
                "potential_mitigations": "Validate URLs. Use allowlists for domains. Disable unnecessary protocols.",
                "capec_ids": ["CAPEC-664"]
            },
            {
                "cwe_id": "CWE-287",
                "name": "Improper Authentication",
                "description": "When an actor claims to have a given identity, the software does not prove or insufficiently proves that the claim is correct",
                "abstraction": "Class",
                "likelihood": "High",
                "potential_mitigations": "Implement MFA. Use strong authentication mechanisms. Session management.",
                "capec_ids": ["CAPEC-114", "CAPEC-115"]
            },
            {
                "cwe_id": "CWE-798",
                "name": "Use of Hard-coded Credentials",
                "description": "The software contains hard-coded credentials, such as a password or cryptographic key",
                "abstraction": "Base",
                "likelihood": "Medium",
                "potential_mitigations": "Use environment variables. Implement secret management. Rotate credentials regularly.",
                "capec_ids": ["CAPEC-191"]
            },
            {
                "cwe_id": "CWE-502",
                "name": "Deserialization of Untrusted Data",
                "description": "The application deserializes untrusted data without sufficiently verifying that the resulting data will be valid",
                "abstraction": "Base",
                "likelihood": "Medium",
                "potential_mitigations": "Avoid deserialization of untrusted data. Use safe serialization formats. Implement integrity checks.",
                "capec_ids": ["CAPEC-586"]
            },
            {
                "cwe_id": "CWE-327",
                "name": "Use of a Broken or Risky Cryptographic Algorithm",
                "description": "The use of a broken or risky cryptographic algorithm is an unnecessary risk",
                "abstraction": "Base",
                "likelihood": "Medium",
                "potential_mitigations": "Use strong cryptographic algorithms (AES-256, SHA-256). Avoid MD5, SHA1, DES.",
                "capec_ids": ["CAPEC-20"]
            },
            {
                "cwe_id": "CWE-778",
                "name": "Insufficient Logging",
                "description": "The software does not record security-relevant events or does not record them in sufficient detail",
                "abstraction": "Base",
                "likelihood": "Low",
                "potential_mitigations": "Implement comprehensive logging. Log security events. Use centralized logging.",
                "capec_ids": []
            }
        ]

        for data in cwes:
            cwe = CWE(**data)
            self.session.add(cwe)

        self.session.commit()
        logger.info(f"Seeded {len(cwes)} CWEs")

    # ==========================================================================
    # CONTEXT FACTORS
    # ==========================================================================

    def seed_context_factors(self):
        """Seed context factors for risk calculation"""
        logger.info("Seeding context factors...")

        factors = [
            # Environment
            {"factor_type": "environment", "factor_name": "Production", "factor_value": "production", "multiplier": 1.5, "description": "Production environment"},
            {"factor_type": "environment", "factor_name": "Staging", "factor_value": "staging", "multiplier": 1.2, "description": "Staging environment"},
            {"factor_type": "environment", "factor_name": "Development", "factor_value": "dev", "multiplier": 1.0, "description": "Development environment"},

            # Data Sensitivity
            {"factor_type": "data_sensitivity", "factor_name": "Payment Data", "factor_value": "payment", "multiplier": 1.5, "description": "Payment card data (PCI-DSS)"},
            {"factor_type": "data_sensitivity", "factor_name": "PII", "factor_value": "pii", "multiplier": 1.4, "description": "Personally Identifiable Information"},
            {"factor_type": "data_sensitivity", "factor_name": "Health Data", "factor_value": "health", "multiplier": 1.5, "description": "Protected Health Information (HIPAA)"},
            {"factor_type": "data_sensitivity", "factor_name": "General", "factor_value": "general", "multiplier": 1.0, "description": "General data"},

            # Exposure
            {"factor_type": "exposure", "factor_name": "Public Internet", "factor_value": "public_internet", "multiplier": 1.3, "description": "Exposed to public internet"},
            {"factor_type": "exposure", "factor_name": "Internal Network", "factor_value": "internal", "multiplier": 1.0, "description": "Internal network only"},
            {"factor_type": "exposure", "factor_name": "VPN Required", "factor_value": "vpn", "multiplier": 1.1, "description": "VPN access required"},

            # Asset Criticality
            {"factor_type": "asset_criticality", "factor_name": "Critical", "factor_value": "critical", "multiplier": 1.5, "description": "Business-critical asset"},
            {"factor_type": "asset_criticality", "factor_name": "High", "factor_value": "high", "multiplier": 1.3, "description": "High importance"},
            {"factor_type": "asset_criticality", "factor_name": "Medium", "factor_value": "medium", "multiplier": 1.0, "description": "Medium importance"},
            {"factor_type": "asset_criticality", "factor_name": "Low", "factor_value": "low", "multiplier": 0.8, "description": "Low importance"}
        ]

        for data in factors:
            factor = ContextFactor(**data)
            self.session.add(factor)

        self.session.commit()
        logger.info(f"Seeded {len(factors)} context factors")

    # ==========================================================================
    # COMPLIANCE STANDARDS
    # ==========================================================================

    def seed_compliance_standards(self):
        """Seed compliance standards (PCI-DSS, SANS Top 25)"""
        logger.info("Seeding compliance standards...")

        standards = [
            # PCI-DSS v4.0
            {
                "standard_name": "PCI-DSS",
                "version": "v4.0",
                "requirement_id": "Req-6.2",
                "requirement_title": "Secure Development",
                "requirement_text": "Software development personnel working on bespoke and custom software are trained in secure coding techniques",
                "cwe_mapping": ["CWE-89", "CWE-79", "CWE-78"],
                "priority": 1
            },
            {
                "standard_name": "PCI-DSS",
                "version": "v4.0",
                "requirement_id": "Req-6.4",
                "requirement_title": "Security Vulnerabilities",
                "requirement_text": "Public-facing web applications are protected against known attacks",
                "cwe_mapping": ["CWE-89", "CWE-79", "CWE-918"],
                "owasp_mapping": ["A03:2021", "A10:2021"],
                "priority": 1
            },

            # SANS Top 25
            {
                "standard_name": "SANS-25",
                "version": "2023",
                "requirement_id": "SANS-1",
                "requirement_title": "Out-of-bounds Write",
                "requirement_text": "CWE-787: Out-of-bounds Write",
                "cwe_mapping": ["CWE-787"],
                "priority": 1
            },
            {
                "standard_name": "SANS-25",
                "version": "2023",
                "requirement_id": "SANS-2",
                "requirement_title": "Cross-Site Scripting",
                "requirement_text": "CWE-79: Improper Neutralization of Input During Web Page Generation",
                "cwe_mapping": ["CWE-79"],
                "owasp_mapping": ["A03:2021"],
                "priority": 1
            },
            {
                "standard_name": "SANS-25",
                "version": "2023",
                "requirement_id": "SANS-3",
                "requirement_title": "SQL Injection",
                "requirement_text": "CWE-89: Improper Neutralization of Special Elements used in an SQL Command",
                "cwe_mapping": ["CWE-89"],
                "owasp_mapping": ["A03:2021"],
                "priority": 1
            }
        ]

        for data in standards:
            standard = ComplianceStandard(**data)
            self.session.add(standard)

        self.session.commit()
        logger.info(f"Seeded {len(standards)} compliance standards")

    # ==========================================================================
    # COMPLIANCE BENCHMARKS
    # ==========================================================================

    def seed_compliance_benchmarks(self):
        """Seed industry benchmarks"""
        logger.info("Seeding compliance benchmarks...")

        benchmarks = [
            # Finance - OWASP
            {
                "industry_sector": "finance",
                "standard_name": "OWASP",
                "compliance_threshold": 90.0,
                "average_score": 75.0,
                "percentile_25": 60.0,
                "percentile_50": 75.0,
                "percentile_75": 85.0,
                "percentile_90": 92.0,
                "average_remediation_time_days": 45,
                "sample_size": 150,
                "data_year": 2024
            },
            # E-commerce - PCI-DSS
            {
                "industry_sector": "ecommerce",
                "standard_name": "PCI-DSS",
                "compliance_threshold": 100.0,
                "average_score": 85.0,
                "percentile_25": 70.0,
                "percentile_50": 85.0,
                "percentile_75": 95.0,
                "percentile_90": 100.0,
                "average_remediation_time_days": 60,
                "sample_size": 200,
                "data_year": 2024
            },
            # Technology - OWASP
            {
                "industry_sector": "technology",
                "standard_name": "OWASP",
                "compliance_threshold": 85.0,
                "average_score": 80.0,
                "percentile_25": 65.0,
                "percentile_50": 80.0,
                "percentile_75": 90.0,
                "percentile_90": 95.0,
                "average_remediation_time_days": 30,
                "sample_size": 300,
                "data_year": 2024
            }
        ]

        for data in benchmarks:
            benchmark = ComplianceBenchmark(**data)
            self.session.add(benchmark)

        self.session.commit()
        logger.info(f"Seeded {len(benchmarks)} compliance benchmarks")

    # ==========================================================================
    # SAMPLE DATA
    # ==========================================================================

    def seed_sample_cvss(self):
        """Seed sample CVSS scores"""
        logger.info("Seeding sample CVSS scores...")

        scores = [
            {
                "cve_id": "CVE-2023-12345",
                "cvss_version": "v3.1",
                "base_score": 9.8,
                "vector_string": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
                "severity": "Critical",
                "attack_vector": "Network",
                "attack_complexity": "Low",
                "privileges_required": "None",
                "user_interaction": "None",
                "confidentiality_impact": "High",
                "integrity_impact": "High",
                "availability_impact": "High"
            }
        ]

        for data in scores:
            score = CVSSScore(**data)
            self.session.add(score)

        self.session.commit()
        logger.info(f"Seeded {len(scores)} CVSS scores")

    def seed_sample_exploits(self):
        """Seed sample exploit intelligence"""
        logger.info("Seeding sample exploit intelligence...")

        exploits = [
            {
                "cve_id": "CVE-2023-12345",
                "exploit_source": "ExploitDB",
                "exploit_url": "https://www.exploit-db.com/exploits/50000",
                "exploit_maturity": "Functional",
                "epss_score": 0.75,
                "is_actively_exploited": True,
                "cisa_kev": True,
                "public_poc_available": True
            }
        ]

        for data in exploits:
            exploit = ExploitIntelligence(**data)
            self.session.add(exploit)

        self.session.commit()
        logger.info(f"Seeded {len(exploits)} exploit intelligence entries")


def seed_database(session: Session):
    """Main seeder function"""
    seeder = AnalysisKnowledgeSeeder(session)
    seeder.seed_all()


if __name__ == "__main__":
    from data.database.connection import DatabaseConnection

    db = DatabaseConnection()
    session = db.get_session()

    try:
        seed_database(session)
        print("✅ Database seeded successfully!")
    except Exception as e:
        print(f"❌ Seeding failed: {e}")
        session.rollback()
    finally:
        session.close()
