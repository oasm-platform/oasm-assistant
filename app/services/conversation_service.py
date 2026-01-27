from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, delete
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
            llm_config = await LLMManager.resolve_llm_config_async(workspace_id=workspace_id, user_id=user_id)
            llm = LLMManager.get_llm(llm_config=llm_config)
            title_response = await llm.ainvoke(
                ConversationPrompts.get_conversation_title_prompt(question=question)
            )

            async with self.db.get_session() as session:
                result = await session.execute(
                    select(Conversation).filter(Conversation.conversation_id == conversation_id)
                )
                conversation = result.scalars().first()

                if conversation:
                    conversation.title = title_response.content
                    await session.commit()
                    logger.debug("Conversation {} title updated: {}", conversation_id, title_response.content)
        except Exception as e:
            logger.error("Failed to update conversation title: {}", e)
            # We don't bubble up title generation errors to the user as it's a background enhancement task.
            pass

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
            async with self.db.get_session() as session:
                # Ensure IDs are UUID objects
                if isinstance(workspace_id, str):
                    workspace_id = UUID(workspace_id)
                if isinstance(user_id, str):
                    user_id = UUID(user_id)

                stmt = select(Conversation).filter(
                    Conversation.user_id == user_id,
                    Conversation.workspace_id == workspace_id
                )

                if search:
                    search_filter = f"%{search}%"
                    stmt = stmt.filter(
                        (Conversation.title.ilike(search_filter)) | 
                        (Conversation.description.ilike(search_filter))
                    )

                # Count query
                # Not efficient but functional for now. Ideally use func.count()
                count_result = await session.execute(select(Conversation).filter(
                    Conversation.user_id == user_id,
                    Conversation.workspace_id == workspace_id
                )) # Simplified count, search filtering makes this complex for quick refactor. 
                # Proper way:
                # count_stmt = select(func.count()).select_from(Conversation).filter(...)
                
                # For brevity/safety matching logic, let's fetch all then paginate? No, that's bad.
                # Let's do a separate count query or ignore count for now? The generic way:
                # We need to duplicate the filter logic.
                
                # Re-constructing query for count
                from sqlalchemy import func
                count_stmt = select(func.count()).filter(
                    Conversation.user_id == user_id,
                    Conversation.workspace_id == workspace_id
                )
                if search:
                    count_stmt = count_stmt.filter(
                        (Conversation.title.ilike(search_filter)) | 
                        (Conversation.description.ilike(search_filter))
                    )
                
                total_count_res = await session.execute(count_stmt)
                total_count = total_count_res.scalar()

                # Sorting
                sort_col = getattr(Conversation, sort_by, Conversation.updated_at)
                if sort_order.lower() == "desc":
                    stmt = stmt.order_by(sort_col.desc())
                else:
                    stmt = stmt.order_by(sort_col.asc())

                # Pagination
                if limit > 0:
                    offset = (page - 1) * limit
                    stmt = stmt.offset(offset).limit(limit)

                result = await session.execute(stmt)
                conversations = result.scalars().all()
                
                return list(conversations), total_count
        except Exception as e:
            logger.error("Error getting conversations: {}", e)
            raise

    async def update_conversation(self, conversation_id: str, title: str, description: str, workspace_id: UUID, user_id: UUID) -> Optional[Conversation]:
        try:
            async with self.db.get_session() as session:
                # Ensure IDs are UUID objects
                if isinstance(workspace_id, str):
                    workspace_id = UUID(workspace_id)
                if isinstance(user_id, str):
                    user_id = UUID(user_id)
                if isinstance(conversation_id, str):
                    conversation_id = UUID(conversation_id)

                stmt = select(Conversation).filter(
                    Conversation.conversation_id == conversation_id,
                    Conversation.workspace_id == workspace_id,
                    Conversation.user_id == user_id
                )

                result = await session.execute(stmt)
                conversation = result.scalars().first()
                
                if not conversation:
                    return None

                if title:
                    conversation.title = title
                if description:
                    conversation.description = description
                    
                await session.commit()
                await session.refresh(conversation)
                return conversation
        except Exception as e:
            logger.error("Error updating conversation: {}", e)
            raise

    async def delete_conversation(self, conversation_id: str, workspace_id: UUID, user_id: UUID) -> bool:
        try:
            async with self.db.get_session() as session:
                # Ensure IDs are UUID objects
                if isinstance(workspace_id, str):
                    workspace_id = UUID(workspace_id)
                if isinstance(user_id, str):
                    user_id = UUID(user_id)
                if isinstance(conversation_id, str):
                    conversation_id = UUID(conversation_id)

                stmt = select(Conversation).filter(
                    Conversation.conversation_id == conversation_id,
                    Conversation.workspace_id == workspace_id,
                    Conversation.user_id == user_id
                )

                result = await session.execute(stmt)
                conversation = result.scalars().first()
                if not conversation:
                    return False

                await session.delete(conversation)
                await session.commit()
                return True
        except Exception as e:
            logger.error("Error deleting conversation: {}", e)
            raise

    async def delete_conversations(self, workspace_id: UUID, user_id: UUID) -> int:
        try:
            async with self.db.get_session() as session:
                # Ensure IDs are UUID objects
                if isinstance(workspace_id, str):
                    workspace_id = UUID(workspace_id)
                if isinstance(user_id, str):
                    user_id = UUID(user_id)

                # Bulk delete using delete() statement is more efficient
                stmt = delete(Conversation).filter(
                    Conversation.workspace_id == workspace_id,
                    Conversation.user_id == user_id
                )
                
                result = await session.execute(stmt)
                await session.commit()
                return result.rowcount
        except Exception as e:
            logger.error("Error deleting conversations: {}", e)
            raise
