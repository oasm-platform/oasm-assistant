import json
import uuid
import asyncio
from typing import AsyncGenerator, Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime

from data.database import postgres_db as database_instance
from common.logger import logger
from data.database.models import Message, Conversation, LLMConfig
from agents.workflows.security_coordinator import SecurityCoordinator
from app.protos import assistant_pb2
from app.services.conversation_service import ConversationService
from llms import LLMManager
from data.embeddings import embeddings_manager
from app.services.streaming_handler_service import StreamingResponseBuilder, StreamingMessageHandler
from common.config import configs

class MessageService:
    """Message service with OASM security agent integration"""

    def __init__(self):
        self.db = database_instance
        self.embeddings_manager = embeddings_manager
        self.conversation_service = ConversationService()

    async def get_messages(self, conversation_id: str, workspace_id: UUID, user_id: UUID) -> List[Message]:
        try:
            with self.db.get_session() as session:
                query = session.query(Message).join(Conversation).filter(
                    Message.conversation_id == conversation_id,
                    Conversation.workspace_id == workspace_id,
                    Conversation.user_id == user_id
                ).order_by(Message.created_at.asc())  # Sort oldest first
                messages = query.all()
                session.expunge_all()
                return messages
        except Exception as e:
            logger.error(f"Error getting messages: {e}")
            raise

    async def create_message_stream(
        self, 
        workspace_id: UUID, 
        user_id: UUID, 
        question: str, 
        conversation_id: Optional[str] = None, 
        is_create_conversation: bool = False,
        agent_type: int = 0,
        model: str = "",
        provider: str = "",
        api_key: str = ""
    ):
        """Yields tuple (stream_message, conversation_obj)"""
        # Generate message_id
        message_id = str(uuid.uuid4())
        accumulated_answer = []

        if not conversation_id or is_create_conversation:
            is_create_conversation = True

        with self.db.get_session() as session:
            # Handle conversation creation
            if is_create_conversation:
                conversation = Conversation(
                    workspace_id=workspace_id,
                    user_id=user_id,
                    title="New conversation"
                )
                session.add(conversation)
                session.commit()
                session.refresh(conversation)
                conversation_id = str(conversation.conversation_id)

                asyncio.create_task(
                    self.conversation_service.update_conversation_title_async(
                        conversation_id, question, workspace_id=workspace_id, user_id=user_id
                    )
                )
            else:
                conversation = session.query(Conversation).filter(
                    Conversation.conversation_id == conversation_id,
                    Conversation.workspace_id == workspace_id,
                    Conversation.user_id == user_id
                ).first()
                if not conversation:
                    raise ValueError("Conversation not found")

            # Need to detach conversation to use it outside session or copy needed fields
            # For streaming, we need properties.
            # We can create a simple dict or object to carry conversation info
            conversation_data = {
                "conversation_id": str(conversation.conversation_id),
                "title": conversation.title or "",
                "description": conversation.description or "",
                "created_at": conversation.created_at,
                "updated_at": conversation.updated_at
            }
            
            # Determine LLM configuration
            llm_config = LLMManager.resolve_llm_config(
                provider=provider,
                model=model,
                api_key=api_key,
                workspace_id=workspace_id,
                user_id=user_id
            )

            coordinator = SecurityCoordinator(
                db_session=session,
                workspace_id=workspace_id,
                user_id=user_id,
                llm_config=llm_config
            )

            try:
                agent_key = "orchestration"
                if agent_type == 1:
                    agent_key = "nuclei"
                elif agent_type == 2:
                    agent_key = "analysis"

                streaming_events = coordinator.process_message_question_streaming(
                    question, 
                    conversation_id=conversation_id,
                    agent_type=agent_key
                )

                # Convert conversation_data to proto
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

                    # Update conversation if it's the first response
                    if pb_conversation:
                        stream_message.conversation.CopyFrom(pb_conversation)
                        pb_conversation = None # Only send once

                    # IMPORTANT: Save complete message BEFORE the stream officially 'ends' for the client
                    # This prevents the race condition where frontend refetches BEFORE the DB commit is done.
                    if stream_message.type == "message_end":
                        try:
                            answer = "".join(accumulated_answer)
                            embedding = await self.embeddings_manager.generate_message_embedding_async(question, answer)

                            message = Message(
                                conversation_id=conversation_id,
                                question=question,
                                answer=answer,
                                embedding=embedding
                            )
                            session.add(message)
                            session.commit()
                            logger.debug(f"Message {message.message_id} created and saved to database (pre-done yield)")
                            
                            # Update LangGraph memory
                            await coordinator.update_memory(conversation_id, question, answer)
                        except Exception as save_err:
                            logger.error(f"Failed to auto-save message during stream: {save_err}")

                    yield stream_message

            except Exception as agent_error:
                logger.error(f"Security agent processing failed: {agent_error}", exc_info=True)
                # Stream error response
                handler = StreamingMessageHandler(message_id, conversation_id, question)
                
                error_msg = handler.error(
                    error_type="AgentProcessingError",
                    error_message=LLMManager.get_friendly_error_message(agent_error),
                    agent="MessageService",
                    recoverable=True,
                    retry_suggested=True
                )
                
                yield assistant_pb2.CreateMessageResponse(
                    message_id=message_id,
                    conversation_id=conversation_id,
                    content=error_msg.content,
                    type="error",
                    created_at=datetime.utcnow().isoformat()
                )


    async def update_message_stream(
        self,
        workspace_id: UUID,
        user_id: UUID,
        conversation_id: str,
        message_id: str,
        new_question: str,
        agent_type: int = 0
    ):
        """Yields UpdateMessageResponse"""
        accumulated_answer = []

        with self.db.get_session() as session:
            message = session.query(Message).join(Conversation).filter(
                Message.message_id == message_id,
                Message.conversation_id == conversation_id,
                Conversation.workspace_id == workspace_id,
                Conversation.user_id == user_id
            ).first()

            if not message:
                raise ValueError("Message not found")

            old_question = message.question

            if old_question.strip() != new_question.strip():
                # Regenerate
                llm_config = LLMManager.resolve_llm_config(
                    workspace_id=workspace_id,
                    user_id=user_id
                )

                coordinator = SecurityCoordinator(
                    db_session=session,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    llm_config=llm_config
                )

                # Handled by LangGraph checkpointer in SecurityCoordinator using conversation_id
                try:
                    agent_key = "orchestration"
                    if agent_type == 1:
                        agent_key = "nuclei"
                    elif agent_type == 2:
                        agent_key = "analysis"

                    streaming_events = coordinator.process_message_question_streaming(
                        new_question, 
                        conversation_id=conversation_id,
                        agent_type=agent_key
                    )
                    async_stream = StreamingResponseBuilder.build_response_stream(
                        message_id=message_id,
                        conversation_id=conversation_id,
                        question=new_question,
                        response_generator=streaming_events
                    )

                    async for stream_message in async_stream:
                        if stream_message.type == "text":
                            accumulated_answer.append(stream_message.content)
                        
                        if stream_message.type == "message_end":
                            try:
                                new_answer = "".join(accumulated_answer)
                                message.question = new_question
                                message.answer = new_answer
                                message.embedding = await self.embeddings_manager.generate_message_embedding_async(new_question, new_answer)
                                session.commit()
                                logger.debug(f"Message {message.message_id} updated and saved (pre-done yield)")
                                
                                # Update LangGraph memory
                                await coordinator.update_memory(conversation_id, new_question, new_answer)
                            except Exception as save_err:
                                logger.error(f"Failed to auto-save update during stream: {save_err}")

                        yield assistant_pb2.UpdateMessageResponse(
                            message_id=stream_message.message_id,
                            conversation_id=stream_message.conversation_id,
                            content=stream_message.content,
                            type=stream_message.type
                        )

                except Exception as agent_error:
                    logger.error(f"Error during update: {agent_error}")
                    yield assistant_pb2.UpdateMessageResponse(
                        message_id=message_id,
                        conversation_id=conversation_id,
                        content=str(agent_error),
                        type="error"
                    )

            else:
                # Return existing
                chunk_size = 50
                for i in range(0, len(message.answer), chunk_size):
                    chunk = message.answer[i:i + chunk_size]
                    yield assistant_pb2.UpdateMessageResponse(
                        message_id=message_id,
                        conversation_id=conversation_id,
                        content=chunk,
                        type="text"
                    )


    async def delete_message(self, conversation_id: str, message_id: str, workspace_id: UUID, user_id: UUID) -> bool:
        try:
            with self.db.get_session() as session:
                query = session.query(Message).join(Conversation).filter(
                    Message.message_id == message_id,
                    Message.conversation_id == conversation_id,
                    Conversation.workspace_id == workspace_id,
                    Conversation.user_id == user_id
                )
                message = query.first()
                if not message:
                    return False
                
                session.delete(message)
                session.commit()
                return True
        except Exception as e:
            logger.error(f"Error deleting message: {e}")
            raise
