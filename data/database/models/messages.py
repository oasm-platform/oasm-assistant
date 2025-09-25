from sqlalchemy import ForeignKey, Column, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.types import Float
from sqlalchemy.orm import relationship
from .base import BaseEntity

class Message(BaseEntity):
    __tablename__ = "messages"

    conversation_id = Column("conversationId", UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), index=True)

    question = Column("question", Text, nullable=False)
    answer = Column("answer", Text, nullable=True)
    is_create_template = Column("isCreateTemplate", Boolean, nullable=True, default=False)

    embedding = Column("embedding", ARRAY(Float), nullable=True)

    conversation = relationship("Conversation", back_populates="messages")