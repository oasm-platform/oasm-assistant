from sqlalchemy import ForeignKey, Column, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.types import Float
from sqlalchemy.orm import relationship
from .base import BaseEntity
from uuid import uuid4

class Message(BaseEntity):
    __tablename__ = "messages"
    __table_args__ = {'extend_existing': True} 
    
    message_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.conversation_id", ondelete="CASCADE"), index=True)

    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=True)

    embedding = Column(ARRAY(Float), nullable=True)

    conversation = relationship("Conversation", back_populates="messages")