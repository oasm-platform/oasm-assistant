from common.logger import logger
from grpc import StatusCode
import asyncio
import inspect


class ContextWrapper:
    """Wrapper to add custom attributes to gRPC context"""
    def __init__(self, context, workspace_id, user_id):
        self._context = context
        self.workspace_id = workspace_id
        self.user_id = user_id

    def __getattr__(self, name):
        # Delegate all other attributes to the original context
        return getattr(self._context, name)


def get_metadata_interceptor(func):
    """
    Decorator to extract workspace_id and user_id from gRPC metadata.
    Supports both sync and async functions, and async generators.
    """
    if inspect.isasyncgenfunction(func):
        # Async generator - return the generator itself, don't await it
        async def async_gen_wrapper(self, request, context):
            md = dict(context.invocation_metadata())
            workspace_id = md.get("x-workspace-id")
            user_id = md.get("x-user-id")

            # Check if workspace_id and user_id are present in metadata
            if not workspace_id or not user_id:
                logger.warning("Missing workspace_id or user_id in metadata")
                context.set_code(StatusCode.INVALID_ARGUMENT)
                context.set_details("Missing workspace_id or user_id in metadata")
                return

            # Wrap context with our custom wrapper that adds workspace_id and user_id
            wrapped_context = ContextWrapper(context, workspace_id, user_id)

            # For async generators, yield from the function
            async for item in func(self, request, wrapped_context):
                yield item
        return async_gen_wrapper
    elif asyncio.iscoroutinefunction(func):
        # Async function (not generator)
        async def async_wrapper(self, request, context):
            md = dict(context.invocation_metadata())
            workspace_id = md.get("x-workspace-id")
            user_id = md.get("x-user-id")

            # Check if workspace_id and user_id are present in metadata
            if not workspace_id or not user_id:
                logger.warning("Missing workspace_id or user_id in metadata")
                context.set_code(StatusCode.INVALID_ARGUMENT)
                context.set_details("Missing workspace_id or user_id in metadata")
                return None

            # Wrap context with our custom wrapper that adds workspace_id and user_id
            wrapped_context = ContextWrapper(context, workspace_id, user_id)

            return await func(self, request, wrapped_context)
        return async_wrapper
    else:
        # Sync function
        def sync_wrapper(self, request, context):
            md = dict(context.invocation_metadata())
            workspace_id = md.get("x-workspace-id")
            user_id = md.get("x-user-id")

            # Check if workspace_id and user_id are present in metadata
            if not workspace_id or not user_id:
                logger.warning("Missing workspace_id or user_id in metadata")
                context.set_code(StatusCode.INVALID_ARGUMENT)
                context.set_details("Missing workspace_id or user_id in metadata")
                return None

            # Wrap context with our custom wrapper that adds workspace_id and user_id
            wrapped_context = ContextWrapper(context, workspace_id, user_id)

            return func(self, request, wrapped_context)
        return sync_wrapper