from sqlalchemy import Column, String, Text, Float
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from uuid import uuid4
from .base import BaseEntity

class KnowledgeBase(BaseEntity):

    __tablename__ = "knowledge_base"
    __table_args__ = {'extend_existing': True} 

    knowledge_base_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    text = Column(Text, nullable=False, comment="text")
    embedding = Column(ARRAY(Float), nullable=False, comment="Vector embedding for text")