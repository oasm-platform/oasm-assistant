from uuid import UUID
from app.protos import assistant_pb2, assistant_pb2_grpc
from app.services.conversation_service import ConversationService
from app.interceptors import get_metadata_interceptor
from common.logger import logger
from grpc import StatusCode

class ConversationServicer(assistant_pb2_grpc.ConversationServiceServicer):
    def __init__(self, service: ConversationService = None):
        self.service = service or ConversationService()

    def _conversation_to_proto(self, conversation):
        """Convert SQLAlchemy model to protobuf message"""
        if not conversation:
            return None
            
        try:
            conv_dict = conversation.to_dict()
            
            return assistant_pb2.Conversation(
                conversation_id=str(conv_dict.get('conversation_id', '')),
                title=str(conv_dict.get('title', '')) if conv_dict.get('title') else '',
                description=str(conv_dict.get('description', '')) if conv_dict.get('description') else '',
                created_at=str(conv_dict.get('created_at', '')) if conv_dict.get('created_at') else '',
                updated_at=str(conv_dict.get('updated_at', '')) if conv_dict.get('updated_at') else ''
            )
        except Exception as e:
            logger.error(f"Error converting conversation to proto: {e}", exc_info=True)
            return assistant_pb2.Conversation(
                conversation_id='', title='', description='', created_at='', updated_at=''
            )

    @get_metadata_interceptor
    async def GetConversations(self, request, context):
        try:
            workspace_id = UUID(context.workspace_id)
            user_id = UUID(context.user_id)

            conversations, total_count = await self.service.get_conversations(
                workspace_id=workspace_id, 
                user_id=user_id,
                search=request.search if request.search else None,
                page=request.page if request.page > 0 else 1,
                limit=request.limit if request.limit > 0 else 20,
                sort_by=request.sort_by if request.sort_by else "updated_at",
                sort_order=request.sort_order if request.sort_order else "desc"
            )
            
            conversation_messages = []
            for conv in conversations:
                proto_conv = self._conversation_to_proto(conv)
                if proto_conv and proto_conv.conversation_id:
                    conversation_messages.append(proto_conv)

            return assistant_pb2.GetConversationsResponse(
                conversations=conversation_messages,
                total_count=total_count
            )

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
            workspace_id = UUID(context.workspace_id)
            user_id = UUID(context.user_id)

            conversation = await self.service.update_conversation(
                conversation_id, title, description, workspace_id, user_id
            )

            if not conversation:
                context.set_code(StatusCode.NOT_FOUND)
                context.set_details("Conversation not found")
                return assistant_pb2.UpdateConversationResponse()

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
            workspace_id = UUID(context.workspace_id)
            user_id = UUID(context.user_id)

            success = await self.service.delete_conversation(conversation_id, workspace_id, user_id)

            if not success:
                context.set_code(StatusCode.NOT_FOUND)
                context.set_details("Conversation not found")
                return assistant_pb2.DeleteConversationResponse(message="Conversation not found", success=False)

            return assistant_pb2.DeleteConversationResponse(message="Conversation deleted", success=True)

        except Exception as e:
            logger.error(f"Error deleting conversation: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.DeleteConversationResponse(message=str(e), success=False)

    @get_metadata_interceptor
    async def DeleteConversations(self, request, context):
        try:
            workspace_id = UUID(context.workspace_id)
            user_id = UUID(context.user_id)

            count = await self.service.delete_conversations(workspace_id, user_id)
            return assistant_pb2.DeleteConversationsResponse(message=f"Deleted {count} conversations", success=True)

        except Exception as e:
            logger.error(f"Error deleting conversations: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.DeleteConversationsResponse(message=str(e), success=False)
