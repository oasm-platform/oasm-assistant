from sqlalchemy import Column, String, Text, Float
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from uuid import uuid4
from .base import BaseEntity

class NucleiTemplates(BaseEntity):

    __tablename__ = "nuclei_templates"
    __table_args__ = {'extend_existing': True} 

    template_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    name = Column(String(255), nullable=False, comment="Name template")
    description = Column(Text, comment="description template")
    template = Column(Text, nullable=False, comment="template")
    embedding = Column(ARRAY(Float), nullable=False, comment="Vector embedding for template")
