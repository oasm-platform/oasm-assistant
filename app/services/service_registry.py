import grpc
from app.protos import assistant_pb2_grpc, assistant_pb2
from .health_service import HealthService
from .domain_classifier import DomainClassifier
from common.logger import logger

class ServiceRegistry(assistant_pb2_grpc.AppServiceServicer):
    def __init__(self):
        self.health_service = HealthService()
        self.domain_classifier = DomainClassifier()
        logger.info("ServiceRegistry initialized")
    
    def HealthCheck(self, request, context):
        """Health check endpoint"""
        try:
            return self.health_service.check_health()
        except Exception as e:
            logger.error(f"Health check error: {e}")     
            return assistant_pb2.HealthCheckResponse(
                message="Health check failed"
            )
    
    def DomainClassify(self, request, context):
        """Domain classification endpoint"""
        try:
            domain = request.domain
            
            if not domain:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("Domain is required")
                return assistant_pb2.DomainClassifyResponse(
                    label=[]
                )
            
            result = self.domain_classifier.classify_domain(domain)
            
            # Build response (only using 'label' field from old proto)
            labels = result.get("labels", [])
            
            response = assistant_pb2.DomainClassifyResponse(
                label=labels
            )
            
            logger.info(f"Domain classification completed for {domain}: {labels}")
            return response
            
        except Exception as e:
            logger.error(f"Domain classification error for {request.domain}: {e}")
            
            return assistant_pb2.DomainClassifyResponse(
                label=[]
            )