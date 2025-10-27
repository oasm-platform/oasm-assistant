from sqlalchemy import Column, String, Float, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from uuid import uuid4
from .base import BaseEntity

class ContextFactor(BaseEntity):
    """
    Context factors for risk score calculation
    Environmental, data sensitivity, exposure, asset criticality
    """

    __tablename__ = "context_factors"
    __table_args__ = (
        Index('idx_context_type', 'factor_type'),
        Index('idx_context_name', 'factor_name'),
        {'extend_existing': True}
    )

    factor_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Factor type
    factor_type = Column(String(50), nullable=False, comment="environment, data_sensitivity, exposure, asset_criticality")

    # Factor details
    factor_name = Column(String(100), nullable=False, comment="Specific factor name")
    factor_value = Column(String(100), comment="Factor value (e.g., production, payment)")

    # Risk multiplier
    multiplier = Column(Float, nullable=False, comment="Risk score multiplier (e.g., 1.5)")

    # Description and guidance
    description = Column(Text, comment="Factor description")
    guidance = Column(Text, comment="When to apply this factor")

    # Examples
    examples = Column(Text, comment="Usage examples")
