from app.protos import assistant_pb2, assistant_pb2_grpc
from data.database import db as database_instance
from common.logger import logger
from grpc import StatusCode
from data.database.models import Message

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
            sender_type = request.sender_type
            content = request.content
            embedding = list(request.embedding) if request.embedding else None

            with self.db.get_session() as session:
                message = Message(
                    conversation_id=conversation_id,
                    sender_type=sender_type,
                    content=content,
                    embedding=embedding
                )
                session.add(message)
                session.commit()
                return assistant_pb2.CreateMessageResponse(message=message.to_dict())
        
        except Exception as e:
            logger.error(f"Error creating message: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.CreateMessageResponse()