from app.protos import assistant_pb2, assistant_pb2_grpc

class HealthService(assistant_pb2_grpc.HealthCheckServicer):
    def HealthCheck(self, request, context) -> assistant_pb2.HealthCheckResponse:
        return assistant_pb2.HealthCheckResponse(
            message="ok"
        )