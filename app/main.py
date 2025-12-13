import grpc
import asyncio
import sys
import traceback
import atexit
from grpc_reflection.v1alpha import reflection

from .protos import assistant_pb2_grpc
from .protos import assistant_pb2

from .grpc_server import (
    HealthCheckServicer,
    DomainClassifyServicer,
    ConversationServicer,
    MessageServiceServicer,
    MCPServerServiceServicer,
    NucleiTemplateServiceServicer,
    IssueServicer
)

# Use centralized Knowledge Base Updater
from knowledge.updaters import get_kb_updater

from common.logger import logger
from common.config import configs as settings

async def serve():
    """Start async gRPC server with scheduler"""
    kb_updater = None

    try:
        # Start Knowledge Base Auto Updater
        kb_updater = get_kb_updater()
        await kb_updater.start()

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
        assistant_pb2_grpc.add_HealthCheckServicer_to_server(HealthCheckServicer(), server)
        assistant_pb2_grpc.add_DomainClassifyServicer_to_server(DomainClassifyServicer(), server)
        assistant_pb2_grpc.add_ConversationServiceServicer_to_server(ConversationServicer(), server)
        assistant_pb2_grpc.add_MessageServiceServicer_to_server(MessageServiceServicer(), server)
        assistant_pb2_grpc.add_MCPServerServiceServicer_to_server(MCPServerServiceServicer(), server)
        assistant_pb2_grpc.add_NucleiTemplateServiceServicer_to_server(NucleiTemplateServiceServicer(), server)
        assistant_pb2_grpc.add_IssueServiceServicer_to_server(IssueServicer(), server)

        # Register reflection service   
        SERVICE_NAMES = (
            assistant_pb2.DESCRIPTOR.services_by_name['HealthCheck'].full_name,
            assistant_pb2.DESCRIPTOR.services_by_name['DomainClassify'].full_name,
            assistant_pb2.DESCRIPTOR.services_by_name['ConversationService'].full_name,
            assistant_pb2.DESCRIPTOR.services_by_name['MessageService'].full_name,
            assistant_pb2.DESCRIPTOR.services_by_name['MCPServerService'].full_name,
            assistant_pb2.DESCRIPTOR.services_by_name['NucleiTemplateService'].full_name,
            assistant_pb2.DESCRIPTOR.services_by_name['IssueService'].full_name,
            reflection.SERVICE_NAME,  # reflection service itself
        )
        
        reflection.enable_server_reflection(SERVICE_NAMES, server)
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
            if kb_updater:
                await kb_updater.stop()
            await server.stop(grace=5)
            logger.info("Server stopped")

    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        logger.error(traceback.format_exc())
        if kb_updater:
            await kb_updater.stop()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(serve())