from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from .base import BaseEntity
from uuid import uuid4

class STM(BaseEntity):
    """Short-Term Memory (STM) for conversation context using LangGraph checkpoints"""
    __tablename__ = "stm"
    __table_args__ = {'extend_existing': True}

    stm_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.conversation_id", ondelete="CASCADE"), nullable=False, unique=True)
    checkpoint = Column(JSONB, nullable=False)     # LangGraph checkpoint state
    metadata_ = Column("metadata", JSONB, default={})
    parent_checkpoint_id = Column(String, nullable=True)

    conversation = relationship("Conversation", back_populates="stm")


