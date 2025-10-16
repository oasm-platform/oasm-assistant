import grpc
from concurrent import futures
import sys
import traceback

from .protos import assistant_pb2_grpc

from .services import HealthService, DomainClassifier, ConversationService, MessageService, MCPServerService

from common.logger import logger
from common.config import configs as settings 

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
        assistant_pb2_grpc.add_HealthCheckServicer_to_server(HealthService(), server)
        assistant_pb2_grpc.add_DomainClassifyServicer_to_server(DomainClassifier(), server)
        assistant_pb2_grpc.add_ConversationServiceServicer_to_server(ConversationService(), server)
        assistant_pb2_grpc.add_MessageServiceServicer_to_server(MessageService(), server)
        assistant_pb2_grpc.add_MCPServerServiceServicer_to_server(MCPServerService(), server)
        
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