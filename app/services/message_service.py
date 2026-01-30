import json
import uuid
import asyncio
from typing import AsyncGenerator, Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy import select

from data.database import postgres_db as database_instance
from common.logger import logger
from data.database.models import Message, Conversation
from agents.workflows.security_coordinator import SecurityCoordinator
from app.protos import assistant_pb2
from app.services.conversation_service import ConversationService
from llms import LLMManager
from data.embeddings import embeddings_manager
from app.services.streaming_handler_service import StreamingResponseBuilder, StreamingMessageHandler

class MessageService:
    """Message service with OASM security agent integration"""

    def __init__(self):
        self.db = database_instance
        self.embeddings_manager = embeddings_manager
        self.conversation_service = ConversationService()

    async def get_messages(self, conversation_id: str, workspace_id: UUID, user_id: UUID) -> List[Message]:
        try:
            async with self.db.get_session() as session:
                query = select(Message).join(Conversation).filter(
                    Message.conversation_id == conversation_id,
                    Conversation.workspace_id == workspace_id,
                    Conversation.user_id == user_id
                ).order_by(Message.created_at.asc())
                result = await session.execute(query)
                messages = result.scalars().all()
                return list(messages)
        except Exception as e:
            logger.error(f"Error getting messages: {e}")
            raise

    async def _get_or_create_conversation(self, session, workspace_id: UUID, user_id: UUID, conversation_id: Optional[str], is_create: bool, question: str):
        if not conversation_id or is_create:
            conversation = Conversation(
                workspace_id=workspace_id,
                user_id=user_id,
                title="New conversation"
            )
            session.add(conversation)
            await session.commit()
            await session.refresh(conversation)
            conversation_id = str(conversation.conversation_id)
            
            # Update title asynchronously
            asyncio.create_task(
                self.conversation_service.update_conversation_title_async(
                    conversation_id, question, workspace_id=workspace_id, user_id=user_id
                )
            )
        else:
            result = await session.execute(select(Conversation).filter(
                Conversation.conversation_id == conversation_id,
                Conversation.workspace_id == workspace_id,
                Conversation.user_id == user_id
            ))
            conversation = result.scalars().first()
            if not conversation:
                raise ValueError("Conversation not found")

        return conversation, conversation_id

    async def _create_coordinator(self, session, workspace_id: UUID, user_id: UUID) -> SecurityCoordinator:
        llm_config = await LLMManager.resolve_llm_config_async(
            workspace_id=workspace_id,
            user_id=user_id
        )
        return SecurityCoordinator(
            db_session=session,
            workspace_id=workspace_id,
            user_id=user_id,
            llm_config=llm_config
        )

    async def _stream_response(
        self, 
        coordinator: SecurityCoordinator, 
        question: str, 
        conversation_id: str, 
        message_id: str, 
        agent_type: int,
        session,
        conversation_data: Optional[Dict] = None,
        update_message_obj: Optional[Message] = None
    ):
        """Shared logic for streaming response from agent and saving to DB"""
        agent_key = "orchestration"
        if agent_type == 1:
            agent_key = "nuclei"
        elif agent_type == 2:
            agent_key = "analysis"

        accumulated_answer = []
        
        try:
            streaming_events = coordinator.process_message_question_streaming(
                question, 
                conversation_id=conversation_id,
                agent_type=agent_key
            )

            # Build proto conversation object if this is a new conversation/message
            pb_conversation = None
            if conversation_data:
                pb_conversation = assistant_pb2.Conversation(
                    conversation_id=conversation_data.get("conversation_id"),
                    title=conversation_data.get("title", ""),
                    description=conversation_data.get("description", ""),
                    created_at=conversation_data.get("created_at").isoformat() if conversation_data.get("created_at") else "",
                    updated_at=conversation_data.get("updated_at").isoformat() if conversation_data.get("updated_at") else ""
                )

            async_stream = StreamingResponseBuilder.build_response_stream(
                message_id=message_id,
                conversation_id=conversation_id,
                question=question,
                response_generator=streaming_events
            )

            async for stream_message in async_stream:
                if stream_message.type == "text":
                    accumulated_answer.append(stream_message.content)

                # Attach conversation info to the first message chunk if needed
                if pb_conversation:
                    stream_message.conversation.CopyFrom(pb_conversation)
                    pb_conversation = None

                # Handle completion event
                if stream_message.type == "message_end":
                    try:
                        final_answer = "".join(accumulated_answer)
                        embedding = await self.embeddings_manager.generate_message_embedding_async(question, final_answer)

                        if update_message_obj:
                            # Update existing message
                            update_message_obj.question = question
                            update_message_obj.answer = final_answer
                            update_message_obj.embedding = embedding
                            logger.debug(f"Message {message_id} updated")
                        else:
                            # Create new message
                            new_message = Message(
                                message_id=message_id, # Ensure we use the same ID sent to client
                                conversation_id=conversation_id,
                                question=question,
                                answer=final_answer,
                                embedding=embedding
                            )
                            session.add(new_message)
                            logger.debug(f"Message {message_id} created")

                        await session.commit()
                        
                        # Sync with LangGraph memory
                        await coordinator.update_memory(conversation_id, question, final_answer)
                        
                    except Exception as save_err:
                        logger.error(f"Failed to save message: {save_err}")
                
                yield stream_message

        except Exception as agent_error:
            logger.error(f"Agent processing failed: {agent_error}", exc_info=True)
            handler = StreamingMessageHandler(message_id, conversation_id, question)
            error_msg = handler.error(
                error_type="AgentProcessingError",
                error_message=LLMManager.get_friendly_error_message(agent_error),
                agent="MessageService",
                recoverable=True
            )
            yield assistant_pb2.CreateMessageResponse(
                message_id=message_id,
                conversation_id=conversation_id,
                content=error_msg.content,
                type="error",
                created_at=datetime.utcnow().isoformat()
            )

    async def create_message_stream(
        self, workspace_id: UUID, 
        user_id: UUID, 
        question: str, 
        conversation_id: Optional[str] = None, 
        is_create_conversation: bool = False,
        agent_type: int = 0
    ):
        message_id = str(uuid.uuid4())
        
        async with self.db.get_session() as session:
            conversation, conversation_id = await self._get_or_create_conversation(
                session, workspace_id, user_id, conversation_id, is_create_conversation, question
            )
            
            conversation_data = {
                "conversation_id": str(conversation.conversation_id),
                "title": conversation.title or "",
                "description": conversation.description or "",
                "created_at": conversation.created_at,
                "updated_at": conversation.updated_at
            }

            coordinator = await self._create_coordinator(session, workspace_id, user_id)
            
            async for response in self._stream_response(
                coordinator, question, conversation_id, message_id, agent_type, 
                session, conversation_data=conversation_data
            ):
                yield response

    async def update_message_stream(
        self, workspace_id: UUID, user_id: UUID, conversation_id: str, 
        message_id: str, new_question: str, agent_type: int = 0
    ):
        async with self.db.get_session() as session:
            result = await session.execute(select(Message).join(Conversation).filter(
                Message.message_id == message_id,
                Message.conversation_id == conversation_id,
                Conversation.workspace_id == workspace_id,
                Conversation.user_id == user_id
            ))
            message = result.scalars().first()
            if not message:
                raise ValueError("Message not found")

            if message.question.strip() != new_question.strip():
                # Regenerate answer
                coordinator = await self._create_coordinator(session, workspace_id, user_id)
                
                async for response in self._stream_response(
                    coordinator, new_question, conversation_id, message_id, agent_type, 
                    session, update_message_obj=message
                ):
                    # Map to UpdateMessageResponse if needed, but protobuf definition usually allows duck typing 
                    # if fields match. Let's be explicit to be safe.
                    yield assistant_pb2.UpdateMessageResponse(
                        message_id=response.message_id,
                        conversation_id=response.conversation_id,
                        content=response.content,
                        type=response.type
                    )
            else:
                # Return existing answer in chunks
                chunk_size = 50
                answer = message.answer or ""
                for i in range(0, len(answer), chunk_size):
                    chunk = answer[i:i + chunk_size]
                    yield assistant_pb2.UpdateMessageResponse(
                        message_id=message_id,
                        conversation_id=conversation_id,
                        content=chunk,
                        type="text"
                    )

    async def delete_message(self, conversation_id: str, message_id: str, workspace_id: UUID, user_id: UUID) -> bool:
        try:
            async with self.db.get_session() as session:
                result = await session.execute(select(Message).join(Conversation).filter(
                    Message.message_id == message_id,
                    Message.conversation_id == conversation_id,
                    Conversation.workspace_id == workspace_id,
                    Conversation.user_id == user_id
                ))
                message = result.scalars().first()
                if not message:
                    return False
                
                await session.delete(message)
                await session.commit()
                return True
        except Exception as e:
            logger.error(f"Error deleting message: {e}")
            raise
