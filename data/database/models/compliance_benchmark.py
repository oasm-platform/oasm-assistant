from sqlalchemy import Column, String, Float, Integer, Index
from sqlalchemy.dialects.postgresql import UUID
from uuid import uuid4
from .base import BaseEntity

class ComplianceBenchmark(BaseEntity):
    """
    Industry compliance benchmarks
    Statistical data for comparison and gap analysis
    """

    __tablename__ = "compliance_benchmarks"
    __table_args__ = (
        Index('idx_benchmark_industry', 'industry_sector'),
        Index('idx_benchmark_standard', 'standard_name'),
        {'extend_existing': True}
    )

    benchmark_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Industry classification
    industry_sector = Column(String(100), nullable=False, comment="finance, healthcare, ecommerce, technology, etc.")
    company_size = Column(String(50), comment="small, medium, large, enterprise")

    # Standard reference
    standard_name = Column(String(50), nullable=False, comment="OWASP, PCI-DSS, ISO-27001, etc.")
    standard_version = Column(String(20), comment="Standard version")

    # Benchmark scores
    compliance_threshold = Column(Float, nullable=False, comment="Minimum passing score (0-100)")
    average_score = Column(Float, comment="Industry average score")

    # Percentiles
    percentile_25 = Column(Float, comment="25th percentile score")
    percentile_50 = Column(Float, comment="50th percentile (median) score")
    percentile_75 = Column(Float, comment="75th percentile score")
    percentile_90 = Column(Float, comment="90th percentile score")

    # Time metrics
    average_remediation_time_days = Column(Integer, comment="Average days to achieve compliance")

    # Sample statistics
    sample_size = Column(Integer, comment="Number of organizations in sample")
    data_year = Column(Integer, comment="Year of benchmark data")

    # Additional metrics
    common_gaps = Column(String(500), comment="Most common compliance gaps")
    critical_requirements = Column(String(500), comment="Most critical requirements")
