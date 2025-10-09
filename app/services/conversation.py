from app.protos import assistant_pb2, assistant_pb2_grpc
from data.database import db as database_instance
from common.logger import logger
from grpc import StatusCode
from data.database.models import Conversation
from app.interceptors import get_metadata_interceptor

class ConversationService(assistant_pb2_grpc.ConversationServiceServicer):
    def __init__(self):
        self.db = database_instance

    def _conversation_to_proto(self, conversation):
        """Chuyển đổi từ SQLAlchemy model sang protobuf message"""
        if not conversation:
            return None
            
        conv_dict = conversation.to_dict()
        return assistant_pb2.Conversation(
            conversation_id=conv_dict.get('conversation_id', ''),
            title=conv_dict.get('title', ''),
            description=conv_dict.get('description', ''),
            embedding=str(conv_dict.get('embedding', '')) if conv_dict.get('embedding') else '',
            created_at=conv_dict.get('created_at', ''),
            updated_at=conv_dict.get('updated_at', '')
        )

    @get_metadata_interceptor
    def GetConversations(self, request, context):
        try:
            # Extract workspace_id and user_id from context
            workspace_id = context.workspace_id
            user_id = context.user_id

            with self.db.get_session() as session:
                conversations = session.query(Conversation).filter(Conversation.user_id == user_id,
                    Conversation.workspace_id == workspace_id).all()
                
                conversation_messages = [self._conversation_to_proto(conv) for conv in conversations]
                
                return assistant_pb2.GetConversationsResponse(conversations=conversation_messages)
        
        except Exception as e:
            logger.error(f"Error getting conversations: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.GetConversationsResponse()

    
    @get_metadata_interceptor
    def UpdateConversation(self, request, context):
        try:
            conversation_id = request.conversation_id
            title = request.title
            description = request.description
            
            # Extract workspace_id and user_id from context
            workspace_id = context.workspace_id
            user_id = context.user_id

            with self.db.get_session() as session:
                query = session.query(Conversation).filter(Conversation.conversation_id == conversation_id,
                Conversation.workspace_id == workspace_id,
                Conversation.user_id == user_id)
                
                conversation = query.first()
                if not conversation:
                    context.set_code(StatusCode.NOT_FOUND)
                    context.set_details("Conversation not found")
                    return assistant_pb2.UpdateConversationResponse()
                
                conversation.title = title
                conversation.description = description
                session.commit()
                return assistant_pb2.UpdateConversationResponse(conversation=self._conversation_to_proto(conversation))
        
        except Exception as e:
            logger.error(f"Error updating conversation: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.UpdateConversationResponse()
        
    @get_metadata_interceptor
    def DeleteConversation(self, request, context):
        try:
            conversation_id = request.conversation_id
            
            # Extract workspace_id and user_id from context
            workspace_id = context.workspace_id
            user_id = context.user_id

            with self.db.get_session() as session:
                query = session.query(Conversation).filter(Conversation.conversation_id == conversation_id,
                Conversation.workspace_id == workspace_id,
                Conversation.user_id == user_id)
                
                conversation = query.first()
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
        
    @get_metadata_interceptor
    def DeleteConversations(self, request, context):
        try:
            # Extract workspace_id and user_id from context
            workspace_id = context.workspace_id
            user_id = context.user_id
            
            with self.db.get_session() as session:
                query = session.query(Conversation).filter(Conversation.workspace_id == workspace_id,
                Conversation.user_id == user_id)
                
                conversations = query.all()
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