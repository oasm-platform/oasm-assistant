from app.protos import assistant_pb2, assistant_pb2_grpc
from data.database import postgres_db as database_instance
from common.logger import logger
from grpc import StatusCode
from data.database.models import Message, Conversation
from app.interceptors import get_metadata_interceptor
from agents.workflows.security_coordinator import SecurityCoordinator
from llms.prompts import ConversationPrompts
from llms import llm_manager
from data.embeddings import embeddings_manager
from app.services.streaming_handler import StreamingResponseBuilder
import uuid
import asyncio


def async_generator_to_sync(async_gen):
    """
    Convert async generator to sync generator for gRPC compatibility

    Args:
        async_gen: Async generator to convert

    Yields:
        Items from the async generator
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        while True:
            try:
                yield loop.run_until_complete(async_gen.__anext__())
            except StopAsyncIteration:
                break
    finally:
        loop.close()


class MessageService(assistant_pb2_grpc.MessageServiceServicer):
    """Message service with OASM security agent integration"""

    def __init__(self):
        self.db = database_instance
        self.llm = llm_manager.get_llm()
        self.embeddings_manager = embeddings_manager


    @get_metadata_interceptor
    def GetMessages(self, request, context):
        """Get all messages for a conversation"""
        try:
            conversation_id = request.conversation_id
            # Extract workspace_id and user_id from metadata
            workspace_id = context.workspace_id
            user_id = context.user_id
            
            with self.db.get_session() as session:
                query = session.query(Message).join(Conversation).filter(
                    Message.conversation_id == conversation_id,
                    Conversation.workspace_id == workspace_id,
                    Conversation.user_id == user_id
                )
                
                messages = query.all()
                pb_messages = []
                for msg in messages:
                    pb_msg = assistant_pb2.Message(
                        message_id=str(msg.message_id),
                        question=msg.question,
                        answer=msg.answer,
                        conversation_id=str(msg.conversation_id),
                        created_at=msg.created_at.isoformat() if msg.created_at else "",
                        updated_at=msg.updated_at.isoformat() if msg.updated_at else ""
                    )
                    pb_messages.append(pb_msg)
                return assistant_pb2.GetMessagesResponse(messages=pb_messages)

        except Exception as e:
            logger.error(f"Error getting messages: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.GetMessagesResponse(messages=[])

    @get_metadata_interceptor
    def CreateMessage(self, request, context):
        """Create a message with streaming response using security agents"""
        try:
            # Extract request data
            conversation_id = request.conversation_id
            question = request.question.strip()
            is_create_conversation = request.is_create_conversation

            # Validate input
            if not question:
                context.set_code(StatusCode.INVALID_ARGUMENT)
                context.set_details("Question cannot be empty")
                return

            # Extract workspace_id and user_id from metadata
            workspace_id = context.workspace_id
            user_id = context.user_id

            # Generate message_id
            message_id = str(uuid.uuid4())

            # Accumulated answer for database storage
            accumulated_answer = []

            with self.db.get_session() as session:
                # Handle conversation creation
                if is_create_conversation:
                    title_response = self.llm.invoke(ConversationPrompts.get_conversation_title_prompt(question=question))
                    conversation = Conversation(
                        workspace_id=workspace_id,
                        user_id=user_id,
                        title=title_response.content
                    )
                    session.add(conversation)
                    session.commit()
                    session.refresh(conversation)
                    conversation_id = str(conversation.conversation_id)
                else:
                    conversation = session.query(Conversation).filter(
                        Conversation.conversation_id == conversation_id,
                        Conversation.workspace_id == workspace_id,
                        Conversation.user_id == user_id
                    ).first()
                    if not conversation:
                        context.set_code(StatusCode.NOT_FOUND)
                        context.set_details("Conversation not found")
                        return

                # Initialize SecurityCoordinator
                coordinator = SecurityCoordinator(
                    db_session=session,
                    workspace_id=workspace_id,
                    user_id=user_id
                )

                try:
                    # Create streaming response generator (async)
                    streaming_events = coordinator.process_message_question_streaming(question)

                    # Build async response stream
                    async_stream = StreamingResponseBuilder.build_response_stream(
                        message_id=message_id,
                        conversation_id=conversation_id,
                        question=question,
                        response_generator=streaming_events
                    )

                    # Convert async generator to sync for gRPC
                    for stream_message in async_generator_to_sync(async_stream):
                        # Accumulate delta text for database storage
                        if stream_message.type == "delta":
                            import json
                            content_data = json.loads(stream_message.content)
                            accumulated_answer.append(content_data.get("text", ""))

                        # Yield the streaming message
                        yield assistant_pb2.CreateMessageResponse(message=stream_message)

                    # Save complete message to database
                    answer = "".join(accumulated_answer)
                    embedding = self.embeddings_manager.generate_message_embedding(question, answer)

                    message = Message(
                        conversation_id=conversation_id,
                        question=question,
                        answer=answer,
                        embedding=embedding
                    )
                    session.add(message)
                    session.commit()
                    session.refresh(message)

                    logger.info(f"Message {message.message_id} created and saved to database")

                except Exception as agent_error:
                    logger.error(f"Security agent processing failed: {agent_error}", exc_info=True)
                    # Stream error response
                    from app.services.streaming_handler import StreamingMessageHandler
                    handler = StreamingMessageHandler(message_id, conversation_id, question)

                    yield assistant_pb2.CreateMessageResponse(message=handler.message_start())
                    yield assistant_pb2.CreateMessageResponse(
                        message=handler.error(
                            error_type="AgentProcessingError",
                            error_message=f"I encountered an issue processing your security question: {str(agent_error)[:200]}",
                            agent="MessageService",
                            recoverable=True,
                            retry_suggested=True
                        )
                    )
                    yield assistant_pb2.CreateMessageResponse(message=handler.message_end(success=False))
                    yield assistant_pb2.CreateMessageResponse(message=handler.done(final_status="error"))

        except Exception as e:
            error_msg = "Error in CreateMessage: " + str(e)
            logger.error(error_msg, exc_info=True)
            context.set_code(StatusCode.INTERNAL)
            context.set_details("Internal server error: " + str(e))
            return

    @get_metadata_interceptor
    def UpdateMessage(self, request, context):
        """Update a message with streaming response if question changed"""
        try:
            # Extract request data
            message_id = request.message_id
            new_question = request.question.strip()

            # Validate input
            if not new_question:
                context.set_code(StatusCode.INVALID_ARGUMENT)
                context.set_details("Question cannot be empty")
                return

            # Extract workspace_id and user_id from metadata
            workspace_id = context.workspace_id
            user_id = context.user_id

            logger.info(f"Updating message {message_id}: {new_question[:100]}...")

            # Accumulated answer for database storage
            accumulated_answer = []

            with self.db.get_session() as session:
                # Find message and verify permissions
                message = session.query(Message).join(Conversation).filter(
                    Message.message_id == message_id,
                    Conversation.workspace_id == workspace_id,
                    Conversation.user_id == user_id
                ).first()

                if not message:
                    logger.warning(f"Message {message_id} not found for user {user_id}")
                    context.set_code(StatusCode.NOT_FOUND)
                    context.set_details("Message not found")
                    return

                conversation_id = str(message.conversation_id)
                old_question = message.question

                # If question changed, regenerate answer with streaming
                if old_question.strip() != new_question.strip():
                    logger.info("Question changed, regenerating answer with streaming...")

                    coordinator = SecurityCoordinator(
                        db_session=session,
                        workspace_id=workspace_id,
                        user_id=user_id
                    )

                    try:
                        # Create streaming response (async)
                        streaming_events = coordinator.process_message_question_streaming(new_question)

                        # Build async response stream
                        async_stream = StreamingResponseBuilder.build_response_stream(
                            message_id=message_id,
                            conversation_id=conversation_id,
                            question=new_question,
                            response_generator=streaming_events
                        )

                        # Convert async generator to sync for gRPC
                        for stream_message in async_generator_to_sync(async_stream):
                            # Accumulate delta text
                            if stream_message.type == "delta":
                                import json
                                content_data = json.loads(stream_message.content)
                                accumulated_answer.append(content_data.get("text", ""))

                            yield assistant_pb2.UpdateMessageResponse(message=stream_message)

                        # Update database
                        new_answer = "".join(accumulated_answer)
                        message.question = new_question
                        message.answer = new_answer
                        message.embedding = self.embeddings_manager.generate_message_embedding(new_question, new_answer)

                        session.commit()
                        session.refresh(message)
                        logger.info(f"Message {message_id} updated successfully")

                    except Exception as agent_error:
                        logger.error(f"Security agent processing failed during update: {agent_error}", exc_info=True)
                        # Stream error response
                        from app.services.streaming_handler import StreamingMessageHandler
                        handler = StreamingMessageHandler(message_id, conversation_id, new_question)

                        yield assistant_pb2.UpdateMessageResponse(message=handler.message_start())
                        yield assistant_pb2.UpdateMessageResponse(
                            message=handler.error(
                                error_type="AgentProcessingError",
                                error_message=f"I encountered an issue: {str(agent_error)[:200]}",
                                agent="MessageService",
                                recoverable=True,
                                retry_suggested=True
                            )
                        )
                        yield assistant_pb2.UpdateMessageResponse(message=handler.message_end(success=False))
                        yield assistant_pb2.UpdateMessageResponse(message=handler.done(final_status="error"))

                else:
                    # Question unchanged, return existing message as single stream
                    logger.info("Question unchanged, returning existing answer")
                    from app.services.streaming_handler import StreamingMessageHandler
                    handler = StreamingMessageHandler(message_id, conversation_id, new_question)

                    yield assistant_pb2.UpdateMessageResponse(message=handler.message_start())
                    # Stream existing answer in chunks
                    chunk_size = 50
                    for i in range(0, len(message.answer), chunk_size):
                        chunk = message.answer[i:i + chunk_size]
                        yield assistant_pb2.UpdateMessageResponse(
                            message=handler.delta(text=chunk, agent="MessageService")
                        )
                    yield assistant_pb2.UpdateMessageResponse(message=handler.message_end(success=True))
                    yield assistant_pb2.UpdateMessageResponse(message=handler.done(final_status="success"))

        except Exception as e:
            error_msg = "Error in UpdateMessage: " + str(e)
            logger.error(error_msg, exc_info=True)
            context.set_code(StatusCode.INTERNAL)
            context.set_details("Internal server error: " + str(e))
            return

    @get_metadata_interceptor
    def DeleteMessage(self, request, context):
        """Delete a message"""
        try:
            message_id = request.message_id
            
            # Extract workspace_id and user_id from metadata
            workspace_id = context.workspace_id
            user_id = context.user_id

            with self.db.get_session() as session:
                query = session.query(Message).join(Conversation).filter(
                    Message.message_id == message_id,
                    Conversation.workspace_id == workspace_id,
                    Conversation.user_id == user_id
                )
                
                message = query.first()

                if not message:
                    context.set_code(StatusCode.NOT_FOUND)
                    context.set_details("Message not found")
                    return assistant_pb2.DeleteMessageResponse(message="Message not found", success=False)

                session.delete(message)
                session.commit()
                return assistant_pb2.DeleteMessageResponse(message="Message deleted successfully", success=True)

        except Exception as e:
            logger.error(f"Error deleting message: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.DeleteMessageResponse(message="Error deleting message", success=False)
