from app.protos import assistant_pb2, assistant_pb2_grpc
from data.database import postgres_db 
from common.logger import logger
from grpc import StatusCode
from data.database.models import Conversation
from app.interceptors import get_metadata_interceptor
from llms.prompts import ConversationPrompts
from llms import llm_manager

class ConversationService(assistant_pb2_grpc.ConversationServiceServicer):
    def __init__(self):
        self.db = postgres_db
        self.llm = llm_manager.get_llm()

    async def update_conversation_title_async(self, conversation_id: str, question: str):
        """Generate and update conversation title in background"""
        try:
            title_response = await self.llm.ainvoke(
                ConversationPrompts.get_conversation_title_prompt(question=question)
            )

            with self.db.get_session() as session:
                conversation = session.query(Conversation).filter(
                    Conversation.conversation_id == conversation_id
                ).first()

                if conversation:
                    conversation.title = title_response.content
                    session.commit()
                    logger.info(f"Conversation {conversation_id} title updated: {title_response.content}")
        except Exception as e:
            logger.error(f"Failed to update conversation title: {e}", exc_info=True)

    def _conversation_to_proto(self, conversation):
        """Chuyển đổi từ SQLAlchemy model sang protobuf message"""
        if not conversation:
            return None
            
        try:
            conv_dict = conversation.to_dict()
            
            # Safely extract and convert fields
            conversation_id = str(conv_dict.get('conversation_id', ''))
            title = str(conv_dict.get('title', '')) if conv_dict.get('title') else ''
            description = str(conv_dict.get('description', '')) if conv_dict.get('description') else ''
            created_at = str(conv_dict.get('created_at', '')) if conv_dict.get('created_at') else ''
            updated_at = str(conv_dict.get('updated_at', '')) if conv_dict.get('updated_at') else ''
            
            return assistant_pb2.Conversation(
                conversation_id=conversation_id,
                title=title,
                description=description,
                created_at=created_at,
                updated_at=updated_at
            )
        except Exception as e:
            logger.error(f"Error converting conversation to proto: {e}", exc_info=True)
            logger.error(f"Conversation data: {conversation.__dict__ if hasattr(conversation, '__dict__') else 'N/A'}")
            # Return minimal valid conversation
            return assistant_pb2.Conversation(
                conversation_id='',
                title='',
                description='',
                created_at='',
                updated_at=''
            )

    @get_metadata_interceptor
    async def GetConversations(self, request, context):
        try:
            # Extract workspace_id and user_id from context
            workspace_id = context.workspace_id
            user_id = context.user_id

            with self.db.get_session() as session:
                conversations = session.query(Conversation).filter(Conversation.user_id == user_id,
                    Conversation.workspace_id == workspace_id).all()

                # Convert to proto and filter out invalid ones (with empty conversation_id)
                conversation_messages = []
                for conv in conversations:
                    proto_conv = self._conversation_to_proto(conv)
                    if proto_conv and proto_conv.conversation_id:  # Only add if conversion succeeded and has valid ID
                        conversation_messages.append(proto_conv)

                return assistant_pb2.GetConversationsResponse(conversations=conversation_messages)

        except Exception as e:
            logger.error(f"Error getting conversations: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.GetConversationsResponse()

    
    @get_metadata_interceptor
    async def UpdateConversation(self, request, context):
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
    async def DeleteConversation(self, request, context):
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
    async def DeleteConversations(self, request, context):
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