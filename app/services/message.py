from app.protos import assistant_pb2, assistant_pb2_grpc
from data.database import db as database_instance
from common.logger import logger
from grpc import StatusCode
from data.database.models import Message, Conversation

class MessageService(assistant_pb2_grpc.MessageServiceServicer):

    def __init__(self):
        self.db = database_instance

    def GetMessages(self, request, context):
        try:
            conversation_id = request.conversation_id
            with self.db.get_session() as session:
                messages = session.query(Message).filter(
                    Message.conversation_id == conversation_id
                ).all()
                return assistant_pb2.GetMessagesResponse(messages=[message.to_dict() for message in messages])
        
        except Exception as e:
            logger.error(f"Error getting messages: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.GetMessagesResponse(messages=[])
    
    def CreateMessage(self, request, context):
        try:
            conversation_id = request.conversation_id
            question = request.question

            with self.db.get_session() as session:

                conversation = session.query(Conversation).filter(
                    Conversation.id == conversation_id
                ).first()

                if not conversation:
                    context.set_code(StatusCode.NOT_FOUND)
                    context.set_details("Conversation not found")
                    return assistant_pb2.CreateMessageResponse()
                
                message = Message(
                    conversation_id=conversation_id,
                    question=question
                )
                session.add(message)
                session.commit()
                session.refresh(message)
                return assistant_pb2.CreateMessageResponse(message=message.to_dict())
        
        except Exception as e:
            logger.error(f"Error creating message: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.CreateMessageResponse()
        
    def UpdateMessage(self, request, context):
        try:
            id = request.id
            question = request.question

            with self.db.get_session() as session:
                message = session.query(Message).filter(
                    Message.id == id
                ).first()

                if not message:
                    context.set_code(StatusCode.NOT_FOUND)
                    context.set_details("Message not found")
                    return assistant_pb2.UpdateMessageResponse()
                
                message.question = question
                session.commit()
                session.refresh(message)
                return assistant_pb2.UpdateMessageResponse(message=message.to_dict())
        
        except Exception as e:
            logger.error(f"Error updating message: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.UpdateMessageResponse()
        
    def DeleteMessage(self, request, context):
        try:
            id = request.id

            with self.db.get_session() as session:
                message = session.query(Message).filter(
                    Message.id == id
                ).first()

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