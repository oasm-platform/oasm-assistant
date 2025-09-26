from app.protos import assistant_pb2, assistant_pb2_grpc
from data.database import db as database_instance
from common.logger import logger
from grpc import StatusCode
from data.database.models import Message, Conversation
from app.interceptors import get_metadata_interceptor
from agents.workflows.security_coordinator import SecurityCoordinator
from agents.specialized.nuclei_generation_agent import NucleiGenerationAgent


class MessageService(assistant_pb2_grpc.MessageServiceServicer):
    """Message service with OASM security agent integration"""

    def __init__(self):
        self.db = database_instance

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
        """Create a message with question and answer"""
        try:
            conversation_id = request.conversation_id
            question = request.question
            is_create_template_raw = getattr(request, 'is_create_template', False)
            # Ensure is_create_template is a boolean value
            is_create_template = bool(is_create_template_raw) if is_create_template_raw is not None else False
            
            # Extract workspace_id and user_id from metadata
            workspace_id = context.workspace_id
            user_id = context.user_id

            with self.db.get_session() as session:
                # Check if conversation exists
                query = session.query(Conversation).filter(Conversation.conversation_id == conversation_id,
                Conversation.workspace_id == workspace_id,
                Conversation.user_id == user_id)
                
                conversation = query.first()

                if not conversation:
                    context.set_code(StatusCode.NOT_FOUND)
                    context.set_details("Conversation not found")
                    return assistant_pb2.CreateMessageResponse()

                # Process the question to generate answer using SecurityCoordinator
                coordinator = SecurityCoordinator()
                answer = coordinator.process_message_question(question, is_create_template)

                # Create and save message with both question and answer
                # Ensure is_create_template is converted to boolean
                message = Message(
                    conversation_id=conversation_id,
                    question=question,
                    answer=answer,
                    is_create_template=bool(is_create_template)
                )
                session.add(message)
                session.commit()
                session.refresh(message)

                logger.info(f"Created message with ID: {message.message_id}")
                
                # Create protobuf message response without is_create_template field
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
            logger.error(f"Error creating message: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.CreateMessageResponse()

    @get_metadata_interceptor
    def UpdateMessage(self, request, context):
        """Update a message"""
        try:
            id = request.id
            question = request.question
            
            # Extract workspace_id and user_id from metadata
            workspace_id = context.workspace_id
            user_id = context.user_id

            with self.db.get_session() as session:
                query = session.query(Message).join(Conversation).filter(Message.id == id,
                Conversation.workspace_id == workspace_id,
                Conversation.user_id == user_id)
                
                message = query.first()

                if not message:
                    context.set_code(StatusCode.NOT_FOUND)
                    context.set_details("Message not found")
                    return assistant_pb2.UpdateMessageResponse()

                # Update question
                old_question = message.question
                message.question = question
                # Update is_create_template if provided in request
                if hasattr(request, 'is_create_template'):
                    message.is_create_template = request.is_create_template

                # If question changed significantly, regenerate answer
                if old_question != question:
                    coordinator = SecurityCoordinator()
                    message.answer = coordinator.process_message_question(question, message.is_create_template)

                session.commit()
                session.refresh(message)
                
                # Create protobuf message response without is_create_template field
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
            logger.error(f"Error updating message: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.UpdateMessageResponse()

    @get_metadata_interceptor
    def DeleteMessage(self, request, context):
        """Delete a message"""
        try:
            id = request.id
            
            # Extract workspace_id and user_id from metadata
            workspace_id = context.workspace_id
            user_id = context.user_id

            with self.db.get_session() as session:
                query = session.query(Message).join(Conversation).filter(Message.id == id,
                Conversation.workspace_id == workspace_id,
                Conversation.user_id == user_id)
                
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
