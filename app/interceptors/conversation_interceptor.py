from data.database.models import Conversation
from common.logger import logger
from grpc import StatusCode

def conversation_interceptor(func):
    def wrapper(self, request, context):
        # Extract metadata
        md = dict(context.invocation_metadata())
        workspace_id = md.get("x-workspace-id")
        user_id = md.get("x-user-id")
        conv_id = request.conversation_id

        if not workspace_id or not user_id or not conv_id:
            logger.warning("Missing workspace_id or user_id or id in metadata")
            context.set_code(StatusCode.INVALID_ARGUMENT)
            context.set_details("Missing workspace_id or user_id or id in metadata")
            return None

        # Check if conversation exists
        with self.db.get_session() as session:
            conversation = (
                session.query(Conversation)
                .filter(
                    Conversation.conversation_id == conv_id,
                    Conversation.workspace_id == workspace_id,
                    Conversation.user_id == user_id,
                )
                .first()
            )
            if not conversation:
                logger.warning(f"Conversation not found: {conv_id}, workspace: {workspace_id}")
                context.set_code(StatusCode.NOT_FOUND)
                context.set_details("Conversation not found")
                return None

        # Attach to context for downstream use
        context.workspace_id = workspace_id
        context.user_id = user_id
        context.conversation_id = conv_id

        return func(self, request, context)
    return wrapper
