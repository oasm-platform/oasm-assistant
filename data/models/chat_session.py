from sqlalchemy import UUID, ForeignKey, String, Column

from sqlalchemy.orm import relationship
from .base import BaseEntity


class ChatSession(BaseEntity):
    __tablename__ = "chat_sessions"

    userId = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    title = Column(String(255))

    user = relationship("User", back_populates="chatSessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete")