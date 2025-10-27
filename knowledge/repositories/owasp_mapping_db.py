"""
OWASP mapping repository
Maps vulnerabilities to OWASP Top 10 categories
"""
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from data.database.models.owasp_mapping import OWASPMapping


class OWASPMappingRepository:
    """Repository for OWASP mapping operations"""

    def __init__(self, session: Session):
        self.session = session

    def get_by_cve(self, cve_id: str, owasp_year: int = 2021) -> Optional[OWASPMapping]:
        """Get OWASP mapping for a CVE"""
        return self.session.query(OWASPMapping)\
            .filter(and_(
                OWASPMapping.cve_id == cve_id,
                OWASPMapping.owasp_year == owasp_year
            ))\
            .first()

    def get_by_cwe(self, cwe_id: str, owasp_year: int = 2021) -> List[OWASPMapping]:
        """Get all OWASP mappings for a CWE"""
        return self.session.query(OWASPMapping)\
            .filter(and_(
                OWASPMapping.cwe_id == cwe_id,
                OWASPMapping.owasp_year == owasp_year
            ))\
            .all()

    def get_by_category(self, owasp_category: str, owasp_year: int = 2021) -> List[OWASPMapping]:
        """Get all mappings for an OWASP category"""
        return self.session.query(OWASPMapping)\
            .filter(and_(
                OWASPMapping.owasp_category == owasp_category,
                OWASPMapping.owasp_year == owasp_year
            ))\
            .all()

    def map_vulnerability_to_owasp(
        self,
        cve_id: Optional[str] = None,
        cwe_id: Optional[str] = None,
        owasp_year: int = 2021
    ) -> Optional[Dict]:
        """
        Map vulnerability to OWASP category

        Args:
            cve_id: CVE identifier
            cwe_id: CWE identifier (fallback if CVE not found)
            owasp_year: OWASP Top 10 year

        Returns:
            Dictionary with OWASP mapping or None
        """
        mapping = None

        # Try CVE first
        if cve_id:
            mapping = self.get_by_cve(cve_id, owasp_year)

        # Fallback to CWE
        if not mapping and cwe_id:
            mappings = self.get_by_cwe(cwe_id, owasp_year)
            if mappings:
                # Take the highest confidence mapping
                mapping = max(mappings, key=lambda m: m.confidence or 0)

        if mapping:
            return {
                "owasp_category": mapping.owasp_category,
                "owasp_name": mapping.owasp_name,
                "owasp_year": mapping.owasp_year,
                "severity": mapping.severity,
                "confidence": mapping.confidence,
                "description": mapping.description
            }

        return None

    def get_category_statistics(self, owasp_year: int = 2021) -> Dict:
        """Get statistics for each OWASP category"""
        mappings = self.session.query(OWASPMapping)\
            .filter(OWASPMapping.owasp_year == owasp_year)\
            .all()

        stats = {}
        for mapping in mappings:
            category = mapping.owasp_category
            if category not in stats:
                stats[category] = {
                    "name": mapping.owasp_name,
                    "count": 0,
                    "critical": 0,
                    "high": 0,
                    "medium": 0,
                    "low": 0
                }

            stats[category]["count"] += 1
            severity = (mapping.severity or "").lower()
            if severity in stats[category]:
                stats[category][severity] += 1

        return stats

    def create_mapping(
        self,
        owasp_category: str,
        owasp_name: str,
        owasp_year: int,
        cve_id: Optional[str] = None,
        cwe_id: Optional[str] = None,
        severity: Optional[str] = None,
        confidence: float = 1.0,
        description: Optional[str] = None,
        owasp_type: str = 'web'
    ) -> OWASPMapping:
        """Create a new OWASP mapping"""
        mapping = OWASPMapping(
            cve_id=cve_id,
            cwe_id=cwe_id,
            owasp_category=owasp_category,
            owasp_name=owasp_name,
            owasp_year=owasp_year,
            owasp_type=owasp_type,
            severity=severity,
            confidence=confidence,
            description=description
        )
        self.session.add(mapping)
        self.session.commit()
        return mapping
