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
            workspace_id = request.workspace_id
            with self.db.get_session() as session:
                conversations = session.query(Conversation).filter(
                    Conversation.workspace_id == workspace_id
                ).all()
                return assistant_pb2.GetConversationsResponse(conversations=[conversation.to_dict() for conversation in conversations])
        
        except Exception as e:
            logger.error(f"Error getting conversations: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.GetConversationsResponse()
    
    def CreateConversation(self, request, context):
        try:
            workspace_id = request.workspace_id
            title = request.title
            description = request.description

            with self.db.get_session() as session:
                conversation = Conversation(title=title, description=description, workspace_id=workspace_id)
                session.add(conversation)
                session.commit()
                session.refresh(conversation)
                return assistant_pb2.CreateConversationResponse(conversation=conversation.to_dict())
        
        except Exception as e:
            logger.error(f"Error creating conversation: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.CreateConversationResponse()