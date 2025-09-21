from sqlalchemy import UUID, String, Column

from sqlalchemy.orm import relationship
from .base import BaseEntity


class Conversation(BaseEntity):
    __tablename__ = "conversations"
    title = Column("title", String(255))
    workspace_id = Column("workspaceId", UUID(as_uuid=True))

    messages = relationship("Message", back_populates="conversation", cascade="all, delete")