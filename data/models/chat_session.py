from sqlalchemy import UUID, ForeignKey, String, Column

from sqlalchemy.orm import relationship
from .base import BaseEntity


class ChatSession(BaseEntity):
    __tablename__ = "chat_sessions"
    title = Column("title", String(255))
    workspace_member_id = Column("workspaceMemberId", UUID(as_uuid=True), ForeignKey("workspace_members.id", ondelete="CASCADE"))

    workspace_member = relationship("WorkspaceMembers", back_populates="chat_sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete")