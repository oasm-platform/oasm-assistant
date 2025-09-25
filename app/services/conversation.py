from app.protos import assistant_pb2, assistant_pb2_grpc
from data.database import db as database_instance
from common.logger import logger
from grpc import StatusCode
from data.database.models import Conversation


class ConversationService(assistant_pb2_grpc.ConversationServiceServicer):
    def __init__(self):
        self.db = database_instance

    def GetConversations(self, request, context):
        try:
            with self.db.get_session() as session:
                conversations = session.query(Conversation).all()
                return assistant_pb2.GetConversationsResponse(conversations=[conversation.to_dict() for conversation in conversations])
        
        except Exception as e:
            logger.error(f"Error getting conversations: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.GetConversationsResponse()
    
    def CreateConversation(self, request, context):
        try:
            title = request.title
            description = request.description

            with self.db.get_session() as session:
                conversation = Conversation(title=title, description=description)
                session.add(conversation)
                session.commit()
                session.refresh(conversation)
                return assistant_pb2.CreateConversationResponse(conversation=conversation.to_dict())
        
        except Exception as e:
            logger.error(f"Error creating conversation: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.CreateConversationResponse()
    
    def UpdateConversation(self, request, context):
        try:
            id = request.id
            title = request.title
            description = request.description

            with self.db.get_session() as session:
                conversation = session.query(Conversation).filter(
                    Conversation.id == id
                ).first()
                if not conversation:
                    context.set_code(StatusCode.NOT_FOUND)
                    context.set_details("Conversation not found")
                    return assistant_pb2.UpdateConversationResponse()
                
                conversation.title = title
                conversation.description = description
                session.commit()
                return assistant_pb2.UpdateConversationResponse(conversation=conversation.to_dict())
        
        except Exception as e:
            logger.error(f"Error updating conversation: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.UpdateConversationResponse()
        
    def DeleteConversation(self, request, context):
        try:
            id = request.id

            with self.db.get_session() as session:
                conversation = session.query(Conversation).filter(
                    Conversation.id == id
                ).first()
                if not conversation:
                    context.set_code(StatusCode.NOT_FOUND)
                    context.set_details("Conversation not found")
                    return assistant_pb2.DeleteConversationResponse(
                        message="Conversation not found",
                        success=False 
                    ) 
                
                session.delete(conversation)
                session.commit()
                return assistant_pb2.DeleteConversationResponse(
                    message="Conversation deleted",
                    success=True
                )
        
        except Exception as e:
            logger.error(f"Error deleting conversation: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.DeleteConversationResponse(
                message=str(e),
                success=False 
            )
        

    def DeleteConversations(self, request, context):
        try:
            with self.db.get_session() as session:
                conversations = session.query(Conversation).all()
                for conversation in conversations:
                    session.delete(conversation)
                session.commit()
                return assistant_pb2.DeleteConversationsResponse(
                    message=f"Deleted {len(conversations)} conversations",
                    success=True
                )
        
        except Exception as e:
            logger.error(f"Error deleting conversations: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.DeleteConversationsResponse(
                message=str(e),
                success=False
            )