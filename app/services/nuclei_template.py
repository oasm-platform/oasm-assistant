from langchain_core.messages import HumanMessage
from common.logger import logger
from llms import llm_manager
from app.protos import assistant_pb2, assistant_pb2_grpc
import grpc
from llms.prompts import NucleiGenerationPrompts


class NucleiTemplateService(assistant_pb2_grpc.NucleiTemplateServiceServicer):
    """Service for generating Nuclei security templates using LLM"""

    def __init__(self):
        """Initialize the Nuclei template service"""
        self.llm_manager = llm_manager
        logger.info("NucleiTemplateService initialized")

    def _generate_template_with_llm(self, question: str) -> str:
        """
        Generate Nuclei template using LLM

        Args:
            question: User's request for template generation

        Returns:
            Generated Nuclei template as YAML string
        """
        try:
            llm = self.llm_manager.get_llm()

            # Get prompt from prompts module
            prompt = NucleiGenerationPrompts.get_nuclei_template_generation_prompt(
                question=question
            )

            # Invoke LLM to generate template
            response = llm.invoke([HumanMessage(content=prompt)])

            # Extract template from response
            template = response.content.strip()

            # Clean up markdown code blocks if present
            if template.startswith("```yaml"):
                template = template[7:]  # Remove ```yaml
            elif template.startswith("```"):
                template = template[3:]  # Remove ```

            if template.endswith("```"):
                template = template[:-3]  # Remove trailing ```

            template = template.strip()

            return template

        except Exception as e:
            logger.error(f"Error generating Nuclei template: {e}")
            raise

    def CreateTemplate(self, request, context):
        """
        gRPC endpoint for creating Nuclei templates

        Args:
            request: CreateTemplateRequest containing the question
            context: gRPC context

        Returns:
            CreateTemplateResponse containing the generated template
        """
        try:
            question = request.question

            # Validate input
            if not question or not question.strip():
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("Question is required and cannot be empty")
                return assistant_pb2.CreateTemplateResponse(
                    answer=""
                )
            # Generate template using LLM
            template = self._generate_template_with_llm(question)

            # Build response
            response = assistant_pb2.CreateTemplateResponse(
                answer=template
            )

            return response

        except Exception as e:
            logger.error(f"Error in CreateTemplate endpoint: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Internal error: {str(e)}")

            return assistant_pb2.CreateTemplateResponse(
                answer=f"Error generating template: {str(e)}"
            )
