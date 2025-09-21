from sqlalchemy import CheckConstraint, ForeignKey, String, Column, Text
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.types import Float
from sqlalchemy.orm import relationship
from .base import BaseEntity

class Message(BaseEntity):
    __tablename__ = "messages"

    conversation_id = Column("conversationId", UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), index=True)

    sender_type = Column("senderType", String(10), nullable=False)
    content = Column("content", Text, nullable=False)

    embedding = Column("embedding", ARRAY(Float), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "sender_type IN ('user', 'system')", 
            name="chk_sender_type"
        ),
    )

    conversation = relationship("Conversation", back_populates="messages")
