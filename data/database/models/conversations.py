from sqlalchemy import String, Column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .base import BaseEntity
from uuid import uuid4


class Conversation(BaseEntity):
    __tablename__ = "conversations"
    __table_args__ = {'extend_existing': True} 
    
    conversation_id = Column( UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    title = Column(String(255))
    description = Column(String(255))
    workspace_id = Column(UUID(as_uuid=True))
    user_id = Column(UUID(as_uuid=True))

    messages = relationship("Message", back_populates="conversation", cascade="all, delete")