from sqlalchemy import Column, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from .base import BaseEntity
from typing import List, Optional
from datetime import datetime


class Workspace(BaseEntity):
    __tablename__ = "workspaces"

    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    owner_id = Column("ownerId", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    api_key = Column("apiKey", Text, nullable=True)
    deleted_at = Column("deletedAt", DateTime, nullable=True)
    archived_at = Column("archivedAt", DateTime, nullable=True)

    # Relationships
    owner = relationship("User", back_populates="workspaces")
    workspace_members = relationship("WorkspaceMembers", back_populates="workspace", cascade="all, delete")
    workspace_targets = relationship("WorkspaceTarget", back_populates="workspace", cascade="all, delete")
    workspace_tools = relationship("WorkspaceTool", back_populates="workspace", cascade="all, delete")
    workers = relationship("WorkerInstance", back_populates="workspace", cascade="all, delete")
