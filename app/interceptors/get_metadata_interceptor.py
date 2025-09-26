from common.logger import logger
from grpc import StatusCode

def get_metadata_interceptor(func):
    def wrapper(self, request, context):
        md = dict(context.invocation_metadata())
        workspace_id = md.get("x-workspace-id")
        user_id = md.get("x-user-id")
        
        # Check if workspace_id and user_id are present in metadata
        if not workspace_id or not user_id:
            logger.warning("Missing workspace_id or user_id in metadata")
            context.set_code(StatusCode.BAD_REQUEST)
            context.set_details("Missing workspace_id or user_id in metadata")
            return None
        
        # Attach workspace_id and user_id to context for downstream use
        context.workspace_id = workspace_id
        context.user_id = user_id
        
        return func(self, request, context)
    return wrapper