from sqlalchemy import Column, String, Text, Float
from sqlalchemy.dialects.postgresql import ARRAY

from .base import BaseEntity

class NucleiTemplate(BaseEntity):

    __tablename__ = "nuclei_template_vectors"
    __table_args__ = {'extend_existing': True} 

    name = Column(String(255), nullable=False, comment="Name template")
    description = Column(Text, comment="description template")
    template = Column(Text, nullable=False, comment="template")
    embedding = Column(ARRAY(Float), nullable=False, comment="Vector embedding for template")
