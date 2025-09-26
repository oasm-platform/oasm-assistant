from data.database.models import Message, Conversation
from common.logger import logger
from grpc import StatusCode

def message_interceptor(func):
    def wrapper(self, request, context):
        md = dict(context.invocation_metadata())
        workspace_id = md.get("x-workspace-id")
        user_id = md.get("x-user-id")
        conv_id = request.conversation_id
        msg_id = request.message_id

        if not workspace_id or not user_id or not conv_id or not msg_id:
            logger.warning("Missing workspace_id or user_id or conversation_id or message_id in metadata")
            context.set_code(StatusCode.INVALID_ARGUMENT)
            context.set_details("Missing workspace_id or user_id or conversation_id or message_id in metadata")
            return None

        # Check if message exists with proper join to conversation
        with self.db.get_session() as session:
            message = (
                session.query(Message)
                .join(Conversation, Message.conversation_id == Conversation.conversation_id)
                .filter(
                    Message.message_id == msg_id,
                    Message.conversation_id == conv_id,
                    Conversation.workspace_id == workspace_id,
                    Conversation.user_id == user_id,
                )
                .first()
            )
            if not message:
                logger.warning("Message not found")
                context.set_code(StatusCode.NOT_FOUND)
                context.set_details("Message not found")
                return None

        # Attach to context for downstream use
        context.workspace_id = workspace_id
        context.user_id = user_id
        context.conversation_id = conv_id
        context.message_id = msg_id

        return func(self, request, context)
    return wrapper