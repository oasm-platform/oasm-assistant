from app.protos import assistant_pb2, assistant_pb2_grpc
from app.services.domain_classifier_service import DomainClassifierService
from app.interceptors import get_metadata_interceptor
from common.logger import logger
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

            result = await self.service.classify_domain(domain)
            labels = result.get("labels", [])

            logger.info(f"Domain classification completed for {domain}: {labels}")

            return assistant_pb2.DomainClassifyResponse(labels=labels)

        except Exception as e:
            logger.error(f"Domain classification error for {request.domain}: {e}")
            return assistant_pb2.DomainClassifyResponse(labels=[])
