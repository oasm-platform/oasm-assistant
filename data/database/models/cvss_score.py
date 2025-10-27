from sqlalchemy import Column, String, Float, Index, JSON
from sqlalchemy.dialects.postgresql import UUID
from uuid import uuid4
from .base import BaseEntity

class CVSSScore(BaseEntity):
    """
    CVSS (Common Vulnerability Scoring System) scores
    Supports CVSS v3.1 and v4.0
    """

    __tablename__ = "cvss_scores"
    __table_args__ = (
        Index('idx_cvss_cve', 'cve_id'),
        Index('idx_cvss_severity', 'severity'),
        {'extend_existing': True}
    )

    cvss_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Vulnerability reference
    cve_id = Column(String(50), nullable=False, comment="CVE identifier")

    # CVSS version
    cvss_version = Column(String(10), nullable=False, comment="v3.1 or v4.0")

    # Scores
    base_score = Column(Float, nullable=False, comment="Base score (0.0-10.0)")
    temporal_score = Column(Float, comment="Temporal score")
    environmental_score = Column(Float, comment="Environmental score")

    # Vector string
    vector_string = Column(String(255), nullable=False, comment="CVSS vector string")

    # Severity rating
    severity = Column(String(20), nullable=False, comment="None, Low, Medium, High, Critical")

    # Base metrics (v3.1)
    attack_vector = Column(String(20), comment="Network, Adjacent, Local, Physical")
    attack_complexity = Column(String(20), comment="Low, High")
    privileges_required = Column(String(20), comment="None, Low, High")
    user_interaction = Column(String(20), comment="None, Required")
    scope = Column(String(20), comment="Unchanged, Changed")
    confidentiality_impact = Column(String(20), comment="None, Low, High")
    integrity_impact = Column(String(20), comment="None, Low, High")
    availability_impact = Column(String(20), comment="None, Low, High")

    # Temporal metrics
    exploit_code_maturity = Column(String(20), comment="Not Defined, High, Functional, PoC, Unproven")
    remediation_level = Column(String(20), comment="Not Defined, Unavailable, Workaround, Temporary, Official")
    report_confidence = Column(String(20), comment="Not Defined, Confirmed, Reasonable, Unknown")

    # Environmental metrics (JSON for flexibility)
    environmental_metrics = Column(JSON, comment="Environmental metric adjustments")
