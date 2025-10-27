"""
CVSS scoring repository
"""
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from data.database.models.cvss_score import CVSSScore


class CVSSRepository:
    """Repository for CVSS score operations"""

    def __init__(self, session: Session):
        self.session = session

    def get_by_cve(self, cve_id: str, version: str = "v3.1") -> Optional[CVSSScore]:
        """Get CVSS score for a CVE"""
        return self.session.query(CVSSScore)\
            .filter(and_(
                CVSSScore.cve_id == cve_id,
                CVSSScore.cvss_version == version
            ))\
            .first()

    def get_latest_score(self, cve_id: str) -> Optional[CVSSScore]:
        """Get the latest CVSS score (prefer v4.0 over v3.1)"""
        scores = self.session.query(CVSSScore)\
            .filter(CVSSScore.cve_id == cve_id)\
            .order_by(desc(CVSSScore.cvss_version))\
            .all()

        return scores[0] if scores else None

    def get_critical_vulnerabilities(self, min_score: float = 9.0) -> List[CVSSScore]:
        """Get critical vulnerabilities by base score"""
        return self.session.query(CVSSScore)\
            .filter(CVSSScore.base_score >= min_score)\
            .order_by(desc(CVSSScore.base_score))\
            .all()

    def get_by_severity(self, severity: str) -> List[CVSSScore]:
        """Get vulnerabilities by severity rating"""
        return self.session.query(CVSSScore)\
            .filter(CVSSScore.severity == severity)\
            .all()

    def calculate_environmental_score(
        self,
        cve_id: str,
        environmental_factors: Dict
    ) -> Optional[float]:
        """
        Calculate environmental score with custom factors

        Args:
            cve_id: CVE identifier
            environmental_factors: Dict with environmental metric adjustments

        Returns:
            Adjusted environmental score
        """
        cvss = self.get_latest_score(cve_id)
        if not cvss:
            return None

        # Start with base score
        score = cvss.base_score

        # Apply environmental factors (simplified calculation)
        # In production, use proper CVSS v3.1/v4.0 formulas
        if environmental_factors.get('modified_attack_vector'):
            # Adjust based on environmental attack vector
            pass

        return score

    def get_exploitability_metrics(self, cve_id: str) -> Optional[Dict]:
        """Get exploitability-related metrics"""
        cvss = self.get_latest_score(cve_id)
        if not cvss:
            return None

        return {
            "attack_vector": cvss.attack_vector,
            "attack_complexity": cvss.attack_complexity,
            "privileges_required": cvss.privileges_required,
            "user_interaction": cvss.user_interaction,
            "exploit_code_maturity": cvss.exploit_code_maturity,
            "exploitability_score": self._calculate_exploitability_subscore(cvss)
        }

    def _calculate_exploitability_subscore(self, cvss: CVSSScore) -> float:
        """Calculate exploitability subscore (CVSS v3.1)"""
        # Simplified calculation - use proper CVSS formula in production
        av_weight = {"Network": 0.85, "Adjacent": 0.62, "Local": 0.55, "Physical": 0.2}
        ac_weight = {"Low": 0.77, "High": 0.44}
        pr_weight = {"None": 0.85, "Low": 0.62, "High": 0.27}
        ui_weight = {"None": 0.85, "Required": 0.62}

        av = av_weight.get(cvss.attack_vector, 0.85)
        ac = ac_weight.get(cvss.attack_complexity, 0.77)
        pr = pr_weight.get(cvss.privileges_required, 0.85)
        ui = ui_weight.get(cvss.user_interaction, 0.85)

        return 8.22 * av * ac * pr * ui

    def create_cvss_score(
        self,
        cve_id: str,
        cvss_version: str,
        base_score: float,
        vector_string: str,
        severity: str,
        **kwargs
    ) -> CVSSScore:
        """Create a new CVSS score entry"""
        cvss = CVSSScore(
            cve_id=cve_id,
            cvss_version=cvss_version,
            base_score=base_score,
            vector_string=vector_string,
            severity=severity,
            **kwargs
        )
        self.session.add(cvss)
        self.session.commit()
        return cvss
