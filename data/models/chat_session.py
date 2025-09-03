from sqlalchemy import UUID, ForeignKey, String, Column

from sqlalchemy.orm import relationship
from .base import BaseEntity


class ChatSession(BaseEntity):
    __tablename__ = "chat_sessions"

    user_id = Column("userId", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    title = Column("title", String(255))

    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete")