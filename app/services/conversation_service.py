from typing import List, Optional
from uuid import UUID
from data.database import postgres_db 
from common.logger import logger
from data.database.models import Conversation
from llms.prompts import ConversationPrompts
from llms import llm_manager

class ConversationService:
    def __init__(self):
        self.db = postgres_db
        self.llm = llm_manager.get_llm()

    async def update_conversation_title_async(self, conversation_id: str, question: str):
        """Generate and update conversation title in background"""
        try:
            title_response = await self.llm.ainvoke(
                ConversationPrompts.get_conversation_title_prompt(question=question)
            )

            with self.db.get_session() as session:
                conversation = session.query(Conversation).filter(
                    Conversation.conversation_id == conversation_id
                ).first()

                if conversation:
                    conversation.title = title_response.content
                    session.commit()
                    logger.debug(f"Conversation {conversation_id} title updated: {title_response.content}")
        except Exception as e:
            logger.error(f"Failed to update conversation title: {e}", exc_info=True)

    async def get_conversations(self, workspace_id: UUID, user_id: UUID) -> List[Conversation]:
        try:
            with self.db.get_session() as session:
                conversations = session.query(Conversation).filter(Conversation.user_id == user_id,
                    Conversation.workspace_id == workspace_id).all()
                # Detach objects from session to return them
                session.expunge_all()
                return conversations
        except Exception as e:
            logger.error(f"Error getting conversations: {e}")
            raise

    async def update_conversation(self, conversation_id: str, title: str, description: str, workspace_id: UUID, user_id: UUID) -> Optional[Conversation]:
        try:
            with self.db.get_session() as session:
                query = session.query(Conversation).filter(Conversation.conversation_id == conversation_id,
                Conversation.workspace_id == workspace_id,
                Conversation.user_id == user_id)

                conversation = query.first()
                if not conversation:
                    return None

                conversation.title = title
                conversation.description = description
                session.commit()
                session.refresh(conversation)
                session.expunge(conversation)
                return conversation
        except Exception as e:
            logger.error(f"Error updating conversation: {e}")
            raise

    async def delete_conversation(self, conversation_id: str, workspace_id: UUID, user_id: UUID) -> bool:
        try:
            with self.db.get_session() as session:
                query = session.query(Conversation).filter(Conversation.conversation_id == conversation_id,
                Conversation.workspace_id == workspace_id,
                Conversation.user_id == user_id)

                conversation = query.first()
                if not conversation:
                    return False

                session.delete(conversation)
                session.commit()
                return True
        except Exception as e:
            logger.error(f"Error deleting conversation: {e}")
            raise

    async def delete_conversations(self, workspace_id: UUID, user_id: UUID) -> int:
        try:
            with self.db.get_session() as session:
                query = session.query(Conversation).filter(Conversation.workspace_id == workspace_id,
                Conversation.user_id == user_id)

                conversations = query.all()
                count = len(conversations)
                for conversation in conversations:
                    session.delete(conversation)
                session.commit()
                return count
        except Exception as e:
            logger.error(f"Error deleting conversations: {e}")
            raise
