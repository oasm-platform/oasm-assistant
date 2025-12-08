from app.protos import assistant_pb2, assistant_pb2_grpc
from app.services.issue_service import IssueService
from common.logger import logger
import grpc
from google.protobuf.json_format import MessageToDict

class IssueServicer(assistant_pb2_grpc.IssueServiceServicer):
    def __init__(self, service: IssueService = None):
        self.service = service or IssueService()

    async def ResolveIssueServers(self, request, context):
        try:
            question = request.question
            issue_type = request.issue_type
            
            # Convert Struct to Dict
            metadata = {}
            if request.metadata:
                metadata = MessageToDict(request.metadata, preserving_proto_field_name=True)

            if not question:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("Question is required")
                return assistant_pb2.ResolveIssueResponse(message="")

            # Call business logic
            # Enum IssueType: ISSUE_TYPE_UNSPECIFIED = 0, ISSUE_TYPE_SSL = 1, ISSUE_TYPE_VULNERABILITY = 2
            result_message = await self.service.resolve_issue(question, issue_type, metadata)

            return assistant_pb2.ResolveIssueResponse(message=result_message)

        except Exception as e:
            logger.error(f"Error in ResolveIssueServers: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Internal error: {str(e)}")
            return assistant_pb2.ResolveIssueResponse(message=f"Error: {e}")
