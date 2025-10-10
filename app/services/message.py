from app.protos import assistant_pb2, assistant_pb2_grpc
from data.database import db as database_instance
from common.logger import logger
from grpc import StatusCode
from data.database.models import Message, Conversation
from app.interceptors import get_metadata_interceptor
from agents.workflows.security_coordinator import SecurityCoordinator
from llms.prompts import ConversationPrompts
from llms import llm_manager

class MessageService(assistant_pb2_grpc.MessageServiceServicer):
    """Message service with OASM security agent integration"""

    def __init__(self):
        self.db = database_instance
        self.llm = llm_manager.get_llm()

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
                        embedding=str(msg.embedding) if msg.embedding else "",
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
        """Create a message with question and AI-generated answer using security agents"""
        try:
            # Extract request data
            conversation_id = request.conversation_id
            question = request.question.strip()
            is_create_conversation = request.is_create_conversation

            # Validate input
            if not question:
                context.set_code(StatusCode.INVALID_ARGUMENT)
                context.set_details("Question cannot be empty")
                return assistant_pb2.CreateMessageResponse()

            # Extract workspace_id and user_id from metadata
            workspace_id = context.workspace_id
            user_id = context.user_id

            logger.info(f"Creating message for conversation {conversation_id}: {question[:100]}...")

            with self.db.get_session() as session:
                if is_create_conversation:
                    title_response = self.llm.invoke(ConversationPrompts.get_conversation_title_prompt(question=question))
                    conversation = Conversation(
                    workspace_id=workspace_id,
                    user_id=user_id,
                    title=title_response.content)
                    session.add(conversation)
                    session.commit()
                    session.refresh(conversation)
                else:
                    conversation = session.query(Conversation).filter(
                        Conversation.conversation_id == conversation_id,
                        Conversation.workspace_id == workspace_id,
                        Conversation.user_id == user_id
                    ).first()
                    if not conversation:
                        context.set_code(StatusCode.NOT_FOUND)
                        context.set_details("Conversation not found")
                        return assistant_pb2.CreateMessageResponse()

                # Initialize SecurityCoordinator and process question
                logger.info("Processing question with SecurityCoordinator...")
                coordinator = SecurityCoordinator()

                try:
                    # Generate answer using updated security agents
                    answer = coordinator.process_message_question(question)
                    logger.info(f"Generated answer length: {len(answer)} characters")

                except Exception as agent_error:
                    logger.error(f"Security agent processing failed: {agent_error}")
                    answer = f"I apologize, but I encountered an issue processing your security question: {str(agent_error)[:200]}..."

                # Create and save message
                message = Message(
                    conversation_id=conversation_id,
                    question=question,
                    answer=answer
                )

                session.add(message)
                session.commit()
                session.refresh(message)

                logger.info(f"Message created successfully with ID: {message.message_id}")

                # Build response
                pb_message = assistant_pb2.Message(
                    message_id=str(message.message_id),
                    question=message.question,
                    answer=message.answer,
                    conversation_id=str(message.conversation_id),
                    embedding=str(message.embedding) if message.embedding else "",
                    created_at=message.created_at.isoformat() if message.created_at else "",
                    updated_at=message.updated_at.isoformat() if message.updated_at else ""
                )

                return assistant_pb2.CreateMessageResponse(message=pb_message)

        except Exception as e:
            logger.error(f"Error in CreateMessage: {e}", exc_info=True)
            context.set_code(StatusCode.INTERNAL)
            context.set_details(f"Internal server error: {str(e)}")
            return assistant_pb2.CreateMessageResponse()

    @get_metadata_interceptor
    def UpdateMessage(self, request, context):
        """Update a message and regenerate answer if question changed"""
        try:
            # Extract request data
            message_id = request.message_id
            new_question = request.question.strip()

            # Validate input
            if not new_question:
                context.set_code(StatusCode.INVALID_ARGUMENT)
                context.set_details("Question cannot be empty")
                return assistant_pb2.UpdateMessageResponse()

            # Extract workspace_id and user_id from metadata
            workspace_id = context.workspace_id
            user_id = context.user_id

            logger.info(f"Updating message {message_id}: {new_question[:100]}...")

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
                    return assistant_pb2.UpdateMessageResponse()

                # Store old question for comparison
                old_question = message.question
                message.question = new_question

                # If question changed, regenerate answer
                if old_question.strip() != new_question.strip():
                    logger.info("Question changed, regenerating answer with SecurityCoordinator...")
                    coordinator = SecurityCoordinator()

                    try:
                        # Generate new answer using updated security agents
                        new_answer = coordinator.process_message_question(new_question)
                        message.answer = new_answer
                        logger.info(f"Answer regenerated, length: {len(new_answer)} characters")

                    except Exception as agent_error:
                        logger.error(f"Security agent processing failed during update: {agent_error}")
                        message.answer = f"I apologize, but I encountered an issue processing your updated security question: {str(agent_error)[:200]}..."

                else:
                    logger.info("Question unchanged, keeping existing answer")

                # Save changes
                session.commit()
                session.refresh(message)

                logger.info(f"Message {message_id} updated successfully")

                # Build response
                pb_message = assistant_pb2.Message(
                    message_id=str(message.message_id),
                    question=message.question,
                    answer=message.answer,
                    conversation_id=str(message.conversation_id),
                    embedding=str(message.embedding) if message.embedding else "",
                    created_at=message.created_at.isoformat() if message.created_at else "",
                    updated_at=message.updated_at.isoformat() if message.updated_at else ""
                )

                return assistant_pb2.UpdateMessageResponse(message=pb_message)

        except Exception as e:
            logger.error(f"Error in UpdateMessage: {e}", exc_info=True)
            context.set_code(StatusCode.INTERNAL)
            context.set_details(f"Internal server error: {str(e)}")
            return assistant_pb2.UpdateMessageResponse()

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
