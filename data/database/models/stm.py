from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import JSONB
from .base import BaseEntity

class STM(BaseEntity):
    """Short-Term Memory (STM) for conversation context using LangGraph checkpoints"""
    __tablename__ = "stm"
    __table_args__ = {'extend_existing': True}

    thread_id = Column(String, primary_key=True)  # conversation_id
    checkpoint = Column(JSONB, nullable=False)     # LangGraph checkpoint state
    checkpoint_id = Column(String, nullable=False)
    metadata_ = Column("metadata", JSONB, default={})
    parent_checkpoint_id = Column(String, nullable=True)


