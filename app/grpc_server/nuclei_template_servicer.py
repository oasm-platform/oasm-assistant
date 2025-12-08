from app.protos import assistant_pb2, assistant_pb2_grpc
from app.services.nuclei_template_service import NucleiTemplateService
from common.logger import logger
import grpc

class NucleiTemplateServiceServicer(assistant_pb2_grpc.NucleiTemplateServiceServicer):
    def __init__(self, service: NucleiTemplateService = None):
        self.service = service or NucleiTemplateService()

    async def CreateTemplate(self, request, context):
        try:
            question = request.question
            if not question or not question.strip():
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("Question is required")
                return assistant_pb2.CreateTemplateResponse(answer="")

            template = await self.service.generate_template(question)

            return assistant_pb2.CreateTemplateResponse(answer=template)

        except Exception as e:
            logger.error(f"Error in CreateTemplate: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Internal error: {str(e)}")
            return assistant_pb2.CreateTemplateResponse(answer=f"Error: {e}")
