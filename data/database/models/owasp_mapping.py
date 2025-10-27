from sqlalchemy import Column, String, Integer, Float, Index
from sqlalchemy.dialects.postgresql import UUID
from uuid import uuid4
from .base import BaseEntity

class OWASPMapping(BaseEntity):
    """
    OWASP Top 10 mapping for vulnerabilities
    Maps CVE/CWE to OWASP categories
    """

    __tablename__ = "owasp_mappings"
    __table_args__ = (
        Index('idx_owasp_cve', 'cve_id'),
        Index('idx_owasp_cwe', 'cwe_id'),
        Index('idx_owasp_category', 'owasp_category'),
        {'extend_existing': True}
    )

    mapping_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Source vulnerability
    cve_id = Column(String(50), nullable=True, comment="CVE identifier (e.g., CVE-2023-12345)")
    cwe_id = Column(String(20), nullable=True, comment="CWE identifier (e.g., CWE-89)")

    # OWASP category
    owasp_category = Column(String(20), nullable=False, comment="OWASP category (e.g., A03:2021)")
    owasp_name = Column(String(255), nullable=False, comment="Category name (e.g., Injection)")
    owasp_year = Column(Integer, nullable=False, comment="OWASP Top 10 year (2021, 2017, etc.)")
    owasp_type = Column(String(50), default='web', comment="Type: web, api, mobile")

    # Scoring
    severity = Column(String(20), comment="Severity: Critical, High, Medium, Low")
    confidence = Column(Float, default=1.0, comment="Mapping confidence score (0.0-1.0)")

    # Description
    description = Column(String(500), comment="Mapping description")
