from app.protos import assistant_pb2

class HealthService:
    def check_health(self) -> assistant_pb2.HealthCheckResponse:
        return assistant_pb2.HealthCheckResponse(
            message="ok"
        )