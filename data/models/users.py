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

    name = Column(Text, nullable=False)
    email = Column(Text, unique=True, nullable=False)
    emailVerified = Column(Boolean, nullable=False, default=False)
    image = Column(Text, nullable=True)
    role = Column(Enum(RoleEnum), nullable=False, default=RoleEnum.USER)

    banExpires = Column(Date, nullable=True)
    banned = Column(Boolean, nullable=True)
    banReason = Column(Text, nullable=True)

    sessions = relationship("Session", back_populates="user", cascade="all, delete")
    accounts = relationship("Account", back_populates="user", cascade="all, delete")
    workspaceMembers = relationship("WorkspaceMembers", back_populates="user", cascade="all, delete")
    workspaces = relationship("Workspace", back_populates="owner", cascade="all, delete")
    searchHistory = relationship("SearchHistory", back_populates="user", cascade="all, delete")
    chatSessions = relationship("ChatSession", back_populates="user", cascade="all, delete")