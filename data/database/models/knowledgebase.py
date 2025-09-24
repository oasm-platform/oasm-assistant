from sqlalchemy import Column, String, Text, Float
from sqlalchemy.dialects.postgresql import ARRAY

from .base import BaseEntity

class KnowledgeBase(BaseEntity):

    __tablename__ = "text_vectors"
    __table_args__ = {'extend_existing': True} 

    text = Column(Text, nullable=False, comment="text")
    embedding = Column(ARRAY(Float), nullable=False, comment="Vector embedding for text")