import grpc
from concurrent import futures
import sys
import traceback

from .protos import app_pb2
from .protos import app_pb2_grpc

from .services.health_service import HealthService
from .services.domain_classifier import DomainClassifier
from common.logger import logger
from common.config import settings


class AppServiceServicer(app_pb2_grpc.AppServiceServicer):
    def __init__(self):
        self.health_service = HealthService()
        self.domain_classifier = DomainClassifier()
        logger.info("AppServiceServicer initialized")
    
    def HealthCheck(self, request, context):
        """Health check endpoint"""
        try:
            health_data = self.health_service.check_health()
            
            response = app_pb2.HealthCheckResponse(
                message=health_data["message"]
            )
            return response
        except Exception as e:
            logger.error(f"Health check error: {e}")     
            return app_pb2.HealthCheckResponse(
                message="Health check failed"
            )
    
    def DomainClassify(self, request, context):
        """Domain classification endpoint"""
        try:
            domain = request.domain
            
            if not domain:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("Domain is required")
                return app_pb2.DomainClassifyResponse(
                    label=["unknown"]
                )
            
            result = self.domain_classifier.classify_domain(domain)
            
            # Build response (only using 'label' field from old proto)
            labels = result.get("labels", ["unknown"])
            
            response = app_pb2.DomainClassifyResponse(
                label=labels
            )
            
            logger.info(f"Domain classification completed for {domain}: {labels}")
            return response
            
        except Exception as e:
            logger.error(f"Domain classification error for {request.domain}: {e}")
            
            return app_pb2.DomainClassifyResponse(
                label=["unknown"]
            )

def serve():
    """Start gRPC server"""
    try:
        # Create server
        server = grpc.server(
            futures.ThreadPoolExecutor(max_workers=settings.max_workers),
            options=[
                ('grpc.keepalive_time_ms', 30000),
                ('grpc.keepalive_timeout_ms', 5000),
                ('grpc.keepalive_permit_without_calls', True),
                ('grpc.http2.max_pings_without_data', 0),
                ('grpc.http2.min_time_between_pings_ms', 10000),
                ('grpc.http2.min_ping_interval_without_data_ms', 300000)
            ]
        )
        
        # Add servicer
        app_pb2_grpc.add_AppServiceServicer_to_server(AppServiceServicer(), server)
        
        # Add insecure port
        listen_addr = f"{settings.host}:{settings.port}"
        server.add_insecure_port(listen_addr)
        
        # Start server
        server.start()
        logger.info(f"gRPC server started on {listen_addr}")
        logger.info(f"Service: {settings.service_name} v{settings.version}")
        
        try:
            server.wait_for_termination()
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            logger.info("Shutting down server...")
            server.stop(grace=5)
            logger.info("Server stopped")
            
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    serve()