from sqlalchemy import UUID, ForeignKey, String, Column

from sqlalchemy.orm import relationship
from .base import BaseEntity


class Conversation(BaseEntity):
    __tablename__ = "conversations"
    title = Column("title", String(255))
    workspace_member_id = Column("workspaceMemberId", UUID(as_uuid=True), ForeignKey("workspace_members.id", ondelete="CASCADE"))

    workspace_member = relationship("WorkspaceMembers", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete")