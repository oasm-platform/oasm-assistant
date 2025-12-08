from app.protos import assistant_pb2, assistant_pb2_grpc
from app.services.health_service import HealthService

class HealthCheckServicer(assistant_pb2_grpc.HealthCheckServicer):
    def __init__(self, service: HealthService = None):
        self.service = service or HealthService()

    async def HealthCheck(self, request, context):
        status = await self.service.check_health()
        return assistant_pb2.HealthCheckResponse(message=status)
