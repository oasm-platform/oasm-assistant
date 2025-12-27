from typing import List, Optional
from uuid import UUID
from data.database import postgres_db 
from common.logger import logger
from data.database.models import Conversation
from llms.prompts import ConversationPrompts
from llms import LLMManager

class ConversationService:
    def __init__(self):
        self.db = postgres_db

    async def update_conversation_title_async(self, conversation_id: str, question: str, workspace_id: Optional[UUID] = None, user_id: Optional[UUID] = None):
        """Generate and update conversation title in background"""
        try:
            llm = LLMManager.get_llm(workspace_id=workspace_id, user_id=user_id)
            title_response = await llm.ainvoke(
                ConversationPrompts.get_conversation_title_prompt(question=question)
            )

            with self.db.get_session() as session:
                conversation = session.query(Conversation).filter(
                    Conversation.conversation_id == conversation_id
                ).first()

                if conversation:
                    conversation.title = title_response.content
                    session.commit()
                    logger.debug("Conversation {} title updated: {}", conversation_id, title_response.content)
        except Exception as e:
            logger.error("Failed to update conversation title: {}", e)

    async def get_conversations(
        self, 
        workspace_id: UUID, 
        user_id: UUID,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
        sort_by: str = "updated_at",
        sort_order: str = "desc"
    ) -> tuple[List[Conversation], int]:
        try:
            with self.db.get_session() as session:
                # Ensure IDs are UUID objects
                if isinstance(workspace_id, str):
                    workspace_id = UUID(workspace_id)
                if isinstance(user_id, str):
                    user_id = UUID(user_id)

                query = session.query(Conversation).filter(
                    Conversation.user_id == user_id,
                    Conversation.workspace_id == workspace_id
                )

                if search:
                    search_filter = f"%{search}%"
                    query = query.filter(
                        (Conversation.title.ilike(search_filter)) | 
                        (Conversation.description.ilike(search_filter))
                    )

                total_count = query.count()

                # Sorting
                sort_col = getattr(Conversation, sort_by, Conversation.updated_at)
                if sort_order.lower() == "desc":
                    query = query.order_by(sort_col.desc())
                else:
                    query = query.order_by(sort_col.asc())

                # Pagination
                if limit > 0:
                    offset = (page - 1) * limit
                    query = query.offset(offset).limit(limit)

                conversations = query.all()
                # Detach objects from session to return them
                session.expunge_all()
                return conversations, total_count
        except Exception as e:
            logger.error("Error getting conversations: {}", e)
            raise

    async def update_conversation(self, conversation_id: str, title: str, description: str, workspace_id: UUID, user_id: UUID) -> Optional[Conversation]:
        try:
            with self.db.get_session() as session:
                # Ensure IDs are UUID objects
                if isinstance(workspace_id, str):
                    workspace_id = UUID(workspace_id)
                if isinstance(user_id, str):
                    user_id = UUID(user_id)
                if isinstance(conversation_id, str):
                    conversation_id = UUID(conversation_id)

                query = session.query(Conversation).filter(
                    Conversation.conversation_id == conversation_id,
                    Conversation.workspace_id == workspace_id,
                    Conversation.user_id == user_id
                )

                conversation = query.first()
                if not conversation:
                    return None

                if title:
                    conversation.title = title
                if description:
                    conversation.description = description
                    
                session.commit()
                session.refresh(conversation)
                session.expunge(conversation)
                return conversation
        except Exception as e:
            logger.error("Error updating conversation: {}", e)
            raise

    async def delete_conversation(self, conversation_id: str, workspace_id: UUID, user_id: UUID) -> bool:
        try:
            with self.db.get_session() as session:
                # Ensure IDs are UUID objects
                if isinstance(workspace_id, str):
                    workspace_id = UUID(workspace_id)
                if isinstance(user_id, str):
                    user_id = UUID(user_id)
                if isinstance(conversation_id, str):
                    conversation_id = UUID(conversation_id)

                query = session.query(Conversation).filter(
                    Conversation.conversation_id == conversation_id,
                    Conversation.workspace_id == workspace_id,
                    Conversation.user_id == user_id
                )

                conversation = query.first()
                if not conversation:
                    return False

                session.delete(conversation)
                session.commit()
                return True
        except Exception as e:
            logger.error("Error deleting conversation: {}", e)
            raise

    async def delete_conversations(self, workspace_id: UUID, user_id: UUID) -> int:
        try:
            with self.db.get_session() as session:
                # Ensure IDs are UUID objects
                if isinstance(workspace_id, str):
                    workspace_id = UUID(workspace_id)
                if isinstance(user_id, str):
                    user_id = UUID(user_id)

                query = session.query(Conversation).filter(
                    Conversation.workspace_id == workspace_id,
                    Conversation.user_id == user_id
                )

                conversations = query.all()
                count = len(conversations)
                for conversation in conversations:
                    session.delete(conversation)
                session.commit()
                return count
        except Exception as e:
            logger.error("Error deleting conversations: {}", e)
            raise
