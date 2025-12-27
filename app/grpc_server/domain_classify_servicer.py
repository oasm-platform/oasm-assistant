from app.protos import assistant_pb2, assistant_pb2_grpc
from app.services.domain_classifier_service import DomainClassifierService
from app.interceptors import get_metadata_interceptor
from common.logger import logger
from llms import LLMManager
import grpc

class DomainClassifyServicer(assistant_pb2_grpc.DomainClassifyServicer):
    def __init__(self, service: DomainClassifierService = None):
        self.service = service or DomainClassifierService()

    @get_metadata_interceptor
    async def DomainClassify(self, request, context):
        try:
            domain = request.domain
            logger.info(f"Domain classification request for: {domain}")
            if not domain:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("Domain is required")
                return assistant_pb2.DomainClassifyResponse(labels=[])

            workspace_id = context.workspace_id
            user_id = context.user_id
            result = await self.service.classify_domain(domain, workspace_id=workspace_id, user_id=user_id)
            labels = result.get("labels", [])

            logger.info(f"Domain classification completed for {domain}: {labels}")

            return assistant_pb2.DomainClassifyResponse(labels=labels)

        except Exception as e:
            logger.error("Domain classification error for {}: {}", request.domain, e)
            error_msg = LLMManager.get_friendly_error_message(e)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(error_msg)
            return assistant_pb2.DomainClassifyResponse(labels=[])
