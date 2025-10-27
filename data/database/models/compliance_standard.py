from sqlalchemy import Column, String, Text, Integer, Index
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from uuid import uuid4
from .base import BaseEntity

class ComplianceStandard(BaseEntity):
    """
    Security compliance standards and requirements
    Supports PCI-DSS, ISO 27001, SANS Top 25, NIST, etc.
    """

    __tablename__ = "compliance_standards"
    __table_args__ = (
        Index('idx_compliance_standard', 'standard_name'),
        Index('idx_compliance_requirement', 'requirement_id'),
        {'extend_existing': True}
    )

    standard_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Standard info
    standard_name = Column(String(50), nullable=False, comment="PCI-DSS, ISO-27001, SANS-25, NIST-CSF")
    version = Column(String(20), comment="Standard version (e.g., v4.0)")

    # Requirement details
    requirement_id = Column(String(50), nullable=False, comment="Requirement ID (e.g., Req 6.2)")
    requirement_title = Column(String(500), comment="Requirement title")
    requirement_text = Column(Text, nullable=False, comment="Full requirement text")

    # Control objectives
    control_objectives = Column(ARRAY(String), comment="Control objectives")
    testing_procedures = Column(Text, comment="Testing procedures")

    # Mappings
    cwe_mapping = Column(ARRAY(String), comment="Related CWE IDs")
    owasp_mapping = Column(ARRAY(String), comment="Related OWASP categories")

    # Classification
    category = Column(String(100), comment="Requirement category")
    priority = Column(Integer, comment="Priority level (1-5)")

    # Guidance
    guidance = Column(Text, comment="Implementation guidance")
    examples = Column(Text, comment="Examples and best practices")
