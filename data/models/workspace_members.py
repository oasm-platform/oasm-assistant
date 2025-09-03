from sqlalchemy import Column, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from .base import BaseEntity


class WorkspaceMembers(BaseEntity):
    __tablename__ = "workspace_members"

    workspace_id = Column("workspaceId", UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"))
    user_id = Column("userId", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))

    # Relationships
    workspace = relationship("Workspace", back_populates="workspace_members")
    user = relationship("User", back_populates="workspace_members")