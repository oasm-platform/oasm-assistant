from app.protos import assistant_pb2, assistant_pb2_grpc
from app.services.message_service import MessageService
from app.interceptors import get_metadata_interceptor
from common.logger import logger
from grpc import StatusCode
from uuid import UUID

class MessageServiceServicer(assistant_pb2_grpc.MessageServiceServicer):
    def __init__(self, service: MessageService = None):
        self.service = service or MessageService()

    @get_metadata_interceptor
    async def GetMessages(self, request, context):
        try:
            conversation_id = request.conversation_id
            if not conversation_id or conversation_id.strip() == '':
                context.set_code(StatusCode.INVALID_ARGUMENT)
                context.set_details("conversation_id cannot be empty")
                return assistant_pb2.GetMessagesResponse(messages=[])

            workspace_id = context.workspace_id
            user_id = context.user_id

            messages = await self.service.get_messages(conversation_id, workspace_id, user_id)
            
            pb_messages = []
            for msg in messages:
                pb_msg = assistant_pb2.Message(
                    message_id=str(msg.message_id),
                    question=msg.question,
                    type="message",
                    content=msg.answer if msg.answer else "",
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
    async def CreateMessage(self, request, context):
        try:
            workspace_id = context.workspace_id
            user_id = context.user_id
            question = request.question.strip()
            
            if not question:
                context.set_code(StatusCode.INVALID_ARGUMENT)
                context.set_details("Question cannot be empty")
                return

            stream = self.service.create_message_stream(
                workspace_id, 
                user_id, 
                question, 
                request.conversation_id, 
                request.is_create_conversation
            )

            async for stream_message, conversation_data in stream:
                 # Convert conversation_data to proto
                pb_conversation = assistant_pb2.Conversation(
                    conversation_id=conversation_data.get("conversation_id"),
                    title=conversation_data.get("title", ""),
                    description=conversation_data.get("description", ""),
                    created_at=conversation_data.get("created_at").isoformat() if conversation_data.get("created_at") else "",
                    updated_at=conversation_data.get("updated_at").isoformat() if conversation_data.get("updated_at") else ""
                )
                
                yield assistant_pb2.CreateMessageResponse(
                    message=stream_message,  # stream_message is already protobuf per current service implementation
                    conversation=pb_conversation
                )

        except Exception as e:
            logger.error(f"Error in CreateMessage: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))

    @get_metadata_interceptor
    async def UpdateMessage(self, request, context):
        try:
            workspace_id = context.workspace_id
            user_id = context.user_id
            
            if not request.conversation_id or not request.message_id:
                context.set_code(StatusCode.INVALID_ARGUMENT)
                context.set_details("IDs required")
                return

            stream = self.service.update_message_stream(
                workspace_id,
                user_id,
                request.conversation_id,
                request.message_id,
                request.question.strip()
            )

            async for stream_message in stream:
                yield assistant_pb2.UpdateMessageResponse(message=stream_message)

        except Exception as e:
            logger.error(f"Error in UpdateMessage: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))

    @get_metadata_interceptor
    async def DeleteMessage(self, request, context):
        try:
            workspace_id = context.workspace_id
            user_id = context.user_id
            
            success = await self.service.delete_message(
                request.conversation_id, 
                request.message_id, 
                workspace_id, 
                user_id
            )

            if not success:
                context.set_code(StatusCode.NOT_FOUND)
                return assistant_pb2.DeleteMessageResponse(message="Message not found", success=False)
            
            return assistant_pb2.DeleteMessageResponse(message="Message deleted", success=True)
            
        except Exception as e:
            logger.error(f"Error deleting message: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.DeleteMessageResponse(message="Error", success=False)
