from sqlalchemy import UUID, ForeignKey, String, Column, Text, JSON, CheckConstraint

from sqlalchemy.orm import relationship
from .base import BaseEntity


class Message(BaseEntity):
    __tablename__ = "messages"

    conversation_id = Column("conversationId", UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"))

    sender_type = Column("senderType", String(10), nullable=False)
    content = Column("content", Text, nullable=False)
    metadata = Column("metadata", JSON)

    __table_args__ = (
        CheckConstraint("senderType IN ('user', 'AI', 'system')", name="chk_sender_type"),
    )

    conversation = relationship("Conversation", back_populates="messages")
