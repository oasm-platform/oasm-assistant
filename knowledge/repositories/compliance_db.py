"""
Compliance standards repository
PCI-DSS, ISO 27001, SANS Top 25, NIST CSF, etc.
"""
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import and_
from data.database.models.compliance_standard import ComplianceStandard


class ComplianceRepository:
    """Repository for compliance standards operations"""

    def __init__(self, session: Session):
        self.session = session

    def get_standard(self, standard_name: str, requirement_id: str) -> Optional[ComplianceStandard]:
        """Get a specific compliance requirement"""
        return self.session.query(ComplianceStandard)\
            .filter(and_(
                ComplianceStandard.standard_name == standard_name,
                ComplianceStandard.requirement_id == requirement_id
            ))\
            .first()

    def get_by_standard(self, standard_name: str, version: Optional[str] = None) -> List[ComplianceStandard]:
        """Get all requirements for a standard"""
        query = self.session.query(ComplianceStandard)\
            .filter(ComplianceStandard.standard_name == standard_name)

        if version:
            query = query.filter(ComplianceStandard.version == version)

        return query.all()

    def get_by_cwe(self, cwe_id: str) -> List[ComplianceStandard]:
        """Get compliance requirements related to a CWE"""
        return self.session.query(ComplianceStandard)\
            .filter(ComplianceStandard.cwe_mapping.contains([cwe_id]))\
            .all()

    def get_by_owasp(self, owasp_category: str) -> List[ComplianceStandard]:
        """Get compliance requirements related to an OWASP category"""
        return self.session.query(ComplianceStandard)\
            .filter(ComplianceStandard.owasp_mapping.contains([owasp_category]))\
            .all()

    def map_vulnerability_to_compliance(
        self,
        cwe_id: Optional[str] = None,
        owasp_category: Optional[str] = None
    ) -> Dict[str, List[ComplianceStandard]]:
        """
        Map vulnerability to compliance requirements

        Returns:
            Dictionary with standard name as key and list of requirements
        """
        requirements = []

        if cwe_id:
            requirements.extend(self.get_by_cwe(cwe_id))

        if owasp_category:
            requirements.extend(self.get_by_owasp(owasp_category))

        # Group by standard
        result = {}
        for req in requirements:
            if req.standard_name not in result:
                result[req.standard_name] = []
            result[req.standard_name].append(req)

        return result

    def check_pci_dss_compliance(self, vulnerabilities: List[Dict]) -> Dict:
        """
        Check PCI-DSS compliance for a list of vulnerabilities

        Args:
            vulnerabilities: List of vulnerability dicts with cwe_id

        Returns:
            PCI-DSS compliance assessment
        """
        all_requirements = self.get_by_standard("PCI-DSS")
        failed_requirements = set()

        for vuln in vulnerabilities:
            cwe_id = vuln.get("cwe_id")
            if cwe_id:
                requirements = self.get_by_cwe(cwe_id)
                for req in requirements:
                    if req.standard_name == "PCI-DSS":
                        failed_requirements.add(req.requirement_id)

        total_requirements = len(all_requirements)
        failed_count = len(failed_requirements)
        passed_count = total_requirements - failed_count

        compliance_score = (passed_count / total_requirements * 100) if total_requirements > 0 else 0

        return {
            "standard": "PCI-DSS",
            "total_requirements": total_requirements,
            "passed": passed_count,
            "failed": failed_count,
            "compliance_score": round(compliance_score, 2),
            "failed_requirements": list(failed_requirements),
            "status": "PASS" if compliance_score >= 100 else "FAIL"
        }

    def get_sans_top25_mapping(self, cwe_id: str) -> Optional[int]:
        """Check if CWE is in SANS Top 25"""
        requirement = self.session.query(ComplianceStandard)\
            .filter(and_(
                ComplianceStandard.standard_name == "SANS-25",
                ComplianceStandard.cwe_mapping.contains([cwe_id])
            ))\
            .first()

        if requirement:
            # Return rank from requirement_id (e.g., "SANS-1" -> 1)
            try:
                return int(requirement.requirement_id.split("-")[1])
            except:
                return None

        return None

    def create_compliance_requirement(
        self,
        standard_name: str,
        requirement_id: str,
        requirement_text: str,
        version: Optional[str] = None,
        cwe_mapping: Optional[List[str]] = None,
        owasp_mapping: Optional[List[str]] = None,
        **kwargs
    ) -> ComplianceStandard:
        """Create a new compliance requirement"""
        requirement = ComplianceStandard(
            standard_name=standard_name,
            requirement_id=requirement_id,
            requirement_text=requirement_text,
            version=version,
            cwe_mapping=cwe_mapping,
            owasp_mapping=owasp_mapping,
            **kwargs
        )
        self.session.add(requirement)
        self.session.commit()
        return requirement
