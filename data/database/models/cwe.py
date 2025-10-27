from sqlalchemy import Column, String, Text, Index
from sqlalchemy.dialects.postgresql import ARRAY
from pgvector.sqlalchemy import Vector
from .base import BaseEntity

class CWE(BaseEntity):
    """
    Common Weakness Enumeration database
    Comprehensive weakness classification system
    """

    __tablename__ = "cwe"
    __table_args__ = (
        Index('idx_cwe_id', 'cwe_id'),
        Index('idx_cwe_name', 'name'),
        {'extend_existing': True}
    )

    cwe_id = Column(String(20), primary_key=True, comment="CWE identifier (e.g., CWE-89)")

    # Basic info
    name = Column(String(500), nullable=False, comment="Weakness name")
    description = Column(Text, nullable=False, comment="Detailed description")
    extended_description = Column(Text, comment="Extended description with examples")

    # Classification
    abstraction = Column(String(20), comment="Base, Variant, Class, Pillar, Category")
    status = Column(String(20), comment="Incomplete, Draft, Stable, Deprecated")

    # Relationships
    parent_cwe_id = Column(String(20), comment="Parent CWE ID")
    child_cwe_ids = Column(ARRAY(String), comment="Child CWE IDs")

    # Attack patterns
    capec_ids = Column(ARRAY(String), comment="Related CAPEC attack pattern IDs")

    # Impact
    likelihood = Column(String(20), comment="Exploitation likelihood: High, Medium, Low")
    technical_impact = Column(ARRAY(String), comment="Technical impacts")

    # Remediation
    potential_mitigations = Column(Text, comment="Mitigation strategies")

    # For semantic search
    embedding = Column(Vector(384), comment="Vector embedding for semantic search")
