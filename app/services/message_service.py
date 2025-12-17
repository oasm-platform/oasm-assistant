import json
import uuid
import asyncio
from typing import AsyncGenerator, Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime

from data.database import postgres_db as database_instance
from common.logger import logger
from data.database.models import Message, Conversation
from agents.workflows.security_coordinator import SecurityCoordinator
from app.services.conversation_service import ConversationService
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
        agent_type: int = 0
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
                    self.conversation_service.update_conversation_title_async(conversation_id, question)
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

            coordinator = SecurityCoordinator(
                db_session=session,
                workspace_id=workspace_id,
                user_id=user_id
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

                async_stream = StreamingResponseBuilder.build_response_stream(
                    message_id=message_id,
                    conversation_id=conversation_id,
                    question=question,
                    response_generator=streaming_events
                )

                async for stream_message in async_stream:
                    if stream_message.type == "delta":
                        content_data = json.loads(stream_message.content)
                        accumulated_answer.append(content_data.get("text", ""))

                    yield stream_message, conversation_data

                # Save complete message
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
                logger.debug(f"Message {message.message_id} created and saved to database")
                
                # Update LangGraph memory
                await coordinator.update_memory(conversation_id, question, answer)

            except Exception as agent_error:
                logger.error(f"Security agent processing failed: {agent_error}", exc_info=True)
                # Stream error response
                handler = StreamingMessageHandler(message_id, conversation_id, question)
                
                # Yield error events
                # Create messages manually since StreamingResponseBuilder is not used here for error
                yield handler.message_start(), conversation_data
                yield handler.error(
                    error_type="AgentProcessingError",
                    error_message=f"I encountered an issue processing your security question: {str(agent_error)[:200]}",
                    agent="MessageService",
                    recoverable=True,
                    retry_suggested=True
                ), conversation_data
                yield handler.message_end(success=False), conversation_data
                yield handler.done(final_status="error"), conversation_data


    async def update_message_stream(
        self,
        workspace_id: UUID,
        user_id: UUID,
        conversation_id: str,
        message_id: str,
        new_question: str,
        agent_type: int = 0
    ):
        """Yields stream_message"""
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
                coordinator = SecurityCoordinator(
                    db_session=session,
                    workspace_id=workspace_id,
                    user_id=user_id
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
                        if stream_message.type == "delta":
                            content_data = json.loads(stream_message.content)
                            accumulated_answer.append(content_data.get("text", ""))
                        yield stream_message

                    new_answer = "".join(accumulated_answer)
                    message.question = new_question
                    message.answer = new_answer
                    message.embedding = await self.embeddings_manager.generate_message_embedding_async(new_question, new_answer)
                    session.commit()
                    
                    # Update LangGraph memory
                    await coordinator.update_memory(conversation_id, new_question, new_answer)

                except Exception as agent_error:
                    logger.error(f"Error during update: {agent_error}")
                    handler = StreamingMessageHandler(message_id, conversation_id, new_question)
                    yield handler.message_start()
                    yield handler.error(
                         error_type="AgentProcessingError",
                         error_message=f"Issue: {str(agent_error)[:200]}",
                         agent="MessageService",
                         recoverable=True,
                         retry_suggested=True
                    )
                    yield handler.message_end(success=False)
                    yield handler.done(final_status="error")

            else:
                # Return existing
                handler = StreamingMessageHandler(message_id, conversation_id, new_question)
                yield handler.message_start()
                chunk_size = 50
                for i in range(0, len(message.answer), chunk_size):
                    chunk = message.answer[i:i + chunk_size]
                    yield handler.delta(text=chunk, agent="MessageService")
                yield handler.message_end(success=True)
                yield handler.done(final_status="success")

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
