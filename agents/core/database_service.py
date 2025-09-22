from typing import Optional, Dict, Any
from uuid import UUID
from sqlalchemy.exc import SQLAlchemyError

from data.database.models import Message, Conversation
from common.logger import logger
from data.database import db as database_instance

class DatabaseService:
    def __init__(self):
        self.db = database_instance
    
    def create_conversation(
        self, 
        title: Optional[str] = None, 
        description: Optional[str] = None,
        workspace_id: Optional[UUID] = None
    ) -> Optional[UUID]:
        """
        Create a new conversation in the database.
        
        Args:
            title: Optional conversation title
            description: Optional conversation description
            workspace_id: Optional workspace identifier
            
        Returns:
            The UUID of the created conversation, or None if creation failed
        """
        try:
            with self.db.get_session() as session:
                conversation = Conversation(
                    title=title or "New Conversation",
                    description=description,
                    workspace_id=workspace_id
                )
                session.add(conversation)
                session.flush()  # Get the ID without committing
                conversation_id = conversation.id
                session.commit()
                
                logger.info(f"Created new conversation with ID: {conversation_id}")
                return conversation_id
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to create conversation: {e}")
            return None
    
    def get_conversation(self, conversation_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Retrieve a conversation by its ID.
        
        Args:
            conversation_id: The UUID of the conversation
            
        Returns:
            Dictionary containing conversation data, or None if not found
        """
        try:
            with self.db.get_session() as session:
                conversation = session.query(Conversation).filter(
                    Conversation.id == conversation_id
                ).first()
                
                if not conversation:
                    return None
                
                return {
                    "id": conversation.id,
                    "title": conversation.title,
                    "description": conversation.description,
                    "workspace_id": conversation.workspace_id,
                    "created_at": conversation.created_at,
                    "updated_at": conversation.updated_at
                }
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to get conversation {conversation_id}: {e}")
            return None
    
    def save_message(
        self, 
        conversation_id: UUID, 
        content: str, 
        sender_type: str
    ) -> Optional[UUID]:
        """
        Save a message to the database.
        
        Args:
            conversation_id: The UUID of the conversation
            content: The message content
            sender_type: Either 'user' or 'system'
            
        Returns:
            The UUID of the created message, or None if creation failed
        """
        try:
            with self.db.get_session() as session:
                message = Message(
                    conversation_id=conversation_id,
                    content=content,
                    sender_type=sender_type
                )
                session.add(message)
                session.flush()
                message_id = message.id
                session.commit()
                
                logger.debug(f"Saved message {message_id} to conversation {conversation_id}")
                return message_id
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to save message: {e}")
            return None
    
    def get_conversation_messages(
        self, 
        conversation_id: UUID, 
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Retrieve messages for a conversation.
        
        Args:
            conversation_id: The UUID of the conversation
            limit: Maximum number of messages to return
            offset: Number of messages to skip
            
        Returns:
            List of message dictionaries ordered by creation time
        """
        try:
            with self.db.get_session() as session:
                query = session.query(Message).filter(
                    Message.conversation_id == conversation_id
                ).order_by(Message.created_at)
                
                if offset > 0:
                    query = query.offset(offset)
                    
                if limit is not None:
                    query = query.limit(limit)
                
                messages = query.all()
                
                return [
                    {
                        "id": msg.id,
                        "content": msg.content,
                        "sender_type": msg.sender_type,
                        "created_at": msg.created_at,
                        "updated_at": msg.updated_at
                    }
                    for msg in messages
                ]
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to get messages for conversation {conversation_id}: {e}")
            return []
    
    def update_conversation(
        self, 
        conversation_id: UUID, 
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> bool:
        """
        Update conversation metadata.
        
        Args:
            conversation_id: The UUID of the conversation
            title: New title (optional)
            description: New description (optional)
            
        Returns:
            True if update was successful, False otherwise
        """
        try:
            with self.db.get_session() as session:
                conversation = session.query(Conversation).filter(
                    Conversation.id == conversation_id
                ).first()
                
                if not conversation:
                    logger.warning(f"Conversation {conversation_id} not found for update")
                    return False
                
                if title is not None:
                    conversation.title = title
                if description is not None:
                    conversation.description = description
                
                session.commit()
                logger.info(f"Updated conversation {conversation_id}")
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to update conversation {conversation_id}: {e}")
            return False
    
    def delete_conversation(self, conversation_id: UUID) -> bool:
        """
        Delete a conversation and all its messages.
        
        Args:
            conversation_id: The UUID of the conversation
            
        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            with self.db.get_session() as session:
                conversation = session.query(Conversation).filter(
                    Conversation.id == conversation_id
                ).first()
                
                if not conversation:
                    logger.warning(f"Conversation {conversation_id} not found for deletion")
                    return False
                
                session.delete(conversation)
                session.commit()
                logger.info(f"Deleted conversation {conversation_id}")
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to delete conversation {conversation_id}: {e}")
            return False
    
    def get_recent_conversations(
        self, 
        workspace_id: Optional[UUID] = None, 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent conversations, optionally filtered by workspace.
        
        Args:
            workspace_id: Optional workspace filter
            limit: Maximum number of conversations to return
            
        Returns:
            List of conversation dictionaries ordered by update time (most recent first)
        """
        try:
            with self.db.get_session() as session:
                query = session.query(Conversation)
                
                if workspace_id is not None:
                    query = query.filter(Conversation.workspace_id == workspace_id)
                
                conversations = query.order_by(
                    Conversation.updated_at.desc()
                ).limit(limit).all()
                
                return [
                    {
                        "id": conv.id,
                        "title": conv.title,
                        "description": conv.description,
                        "workspace_id": conv.workspace_id,
                        "created_at": conv.created_at,
                        "updated_at": conv.updated_at
                    }
                    for conv in conversations
                ]
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to get recent conversations: {e}")
            return []