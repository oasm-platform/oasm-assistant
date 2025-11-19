import grpc
import asyncio
import sys
import traceback
import atexit

from .protos import assistant_pb2_grpc

from .services import (
    HealthService, DomainClassifier, ConversationService, MessageService,
    MCPServerService, NucleiTemplateService, get_scheduler )

from common.logger import logger
from common.config import configs as settings

async def serve():
    """Start async gRPC server with scheduler"""
    scheduler = None

    try:
        # Start Nuclei templates scheduler
        scheduler = get_scheduler()
        scheduler.start()
        logger.info("Nuclei templates scheduler started")

        # Register cleanup handler
        def cleanup():
            if scheduler:
                logger.info("Stopping scheduler...")
                scheduler.stop()
        atexit.register(cleanup)

        # Create ASYNC server
        server = grpc.aio.server(
            options=[
                ('grpc.keepalive_time_ms', 30000),
                ('grpc.keepalive_timeout_ms', 5000),
                ('grpc.keepalive_permit_without_calls', True),
                ('grpc.http2.max_pings_without_data', 0),
                ('grpc.http2.min_time_between_pings_ms', 10000),
                ('grpc.http2.min_ping_interval_without_data_ms', 300000),
                ('grpc.max_concurrent_streams', settings.max_workers)
            ]
        )

        # Add servicers
        assistant_pb2_grpc.add_HealthCheckServicer_to_server(HealthService(), server)
        assistant_pb2_grpc.add_DomainClassifyServicer_to_server(DomainClassifier(), server)
        assistant_pb2_grpc.add_ConversationServiceServicer_to_server(ConversationService(), server)
        assistant_pb2_grpc.add_MessageServiceServicer_to_server(MessageService(), server)
        assistant_pb2_grpc.add_MCPServerServiceServicer_to_server(MCPServerService(), server)
        assistant_pb2_grpc.add_NucleiTemplateServiceServicer_to_server(NucleiTemplateService(), server)

        # Add insecure port
        listen_addr = f"{settings.host}:{settings.port}"
        server.add_insecure_port(listen_addr)

        # Start server
        await server.start()
        logger.info(f"✓ Async gRPC server started on {listen_addr}")
        logger.info(f"Service: {settings.service_name} v{settings.version}")
        logger.info(f"Nuclei templates will sync daily at {settings.scheduler.nuclei_templates_sync_time}")

        try:
            await server.wait_for_termination()
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            logger.info("Shutting down server...")
            if scheduler:
                scheduler.stop()
            await server.stop(grace=5)
            logger.info("Server stopped")

    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        logger.error(traceback.format_exc())
        if scheduler:
            scheduler.stop()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(serve())