from sqlalchemy import (
    Column,
    Boolean,
    Date,
    Text,
)
from sqlalchemy.orm import relationship
from .base import BaseEntity
from common.enums.enum import RoleEnum
from sqlalchemy import Enum

class User(BaseEntity):
    __tablename__ = "users"

    name = Column("name", Text, nullable=False)
    email = Column("email", Text, unique=True, nullable=False)
    email_verified = Column("emailVerified", Boolean, nullable=False, default=False)
    image = Column("image", Text, nullable=True)
    role = Column("role", Enum(RoleEnum), nullable=False, default=RoleEnum.USER)

    ban_expires = Column("banExpires", Date, nullable=True)
    banned = Column("banned", Boolean, nullable=True)
    ban_reason = Column("banReason", Text, nullable=True)

    sessions = relationship("Session", back_populates="user", cascade="all, delete")
    accounts = relationship("Account", back_populates="user", cascade="all, delete")
    workspace_members = relationship("WorkspaceMembers", back_populates="user", cascade="all, delete")
    workspaces = relationship("Workspace", back_populates="owner", cascade="all, delete")
    search_history = relationship("SearchHistory", back_populates="user", cascade="all, delete")
