from langchain_core.messages import HumanMessage
from common.logger import logger
from common.config import configs
from llms import llm_manager
from app.protos import assistant_pb2, assistant_pb2_grpc
import grpc
from llms.prompts import NucleiGenerationPrompts
from data.retrieval import HybridRetriever
from data.indexing.vector_store import PgVectorStore
from data.embeddings import get_embedding_model
from data.retrieval import SimilaritySearcher


class NucleiTemplateService(assistant_pb2_grpc.NucleiTemplateServiceServicer):
    """Service for generating Nuclei security templates using LLM with RAG"""

    def __init__(self):
        """Initialize the Nuclei template service"""
        self.llm_manager = llm_manager

        # Initialize RAG components with shared embedding model (singleton)
        self.vector_store = PgVectorStore()
        shared_embedding = get_embedding_model()

        # Create similarity searcher with shared embedding
        self.similarity_searcher = SimilaritySearcher(
            vector_store=self.vector_store,
            embedding_model=shared_embedding,
            default_metric="cosine",
            ef_search=64
        )

        # Create hybrid retriever with shared similarity searcher
        self.hybrid_retriever = HybridRetriever(
            vector_store=self.vector_store,
            config=configs.embedding,
            similarity_searcher=self.similarity_searcher,
            keyword_weight=0.3,
            vector_weight=0.7
        )

        logger.info("NucleiTemplateService initialized with RAG support")

    def _retrieve_similar_templates(self, question: str, k: int = 5) -> str:
        """
        Retrieve similar templates from database using RAG

        Args:
            question: User's request
            k: Number of similar templates to retrieve

        Returns:
            Formatted context string with similar templates
        """
        try:
            # Try hybrid search first (requires tsv column)
            try:
                results = self.hybrid_retriever.hybrid_search(
                    table="nuclei_templates",
                    qtext=question,
                    k=k,
                    id_col="template_id",
                    title_col="name",
                    content_col="description",
                    embedding_col="embedding",
                    tsv_col="tsv"
                )
            except Exception as hybrid_error:
                # Fallback to vector-only search if tsv column doesn't exist
                logger.debug(f"Hybrid search failed, using vector-only search: {hybrid_error}")
                results = self.hybrid_retriever.similarity_searcher.search(
                    table="nuclei_templates",
                    query=question,
                    k=k,
                    column="embedding",
                    id_col="template_id",
                    meta_cols=["name", "description"]
                )

            if not results:
                return ""

            # Format retrieved templates as context
            context_parts = ["Here are some similar Nuclei templates for reference:\n"]
            for idx, result in enumerate(results, 1):
                # Handle both hybrid search and vector search result formats
                metadata = result.get('metadata', {})
                name = metadata.get('title') or metadata.get('name', 'Unknown')
                description = metadata.get('content') or metadata.get('description', '')

                context_parts.append(f"\n{idx}. Template: {name}")
                if description:
                    context_parts.append(f"   Description: {description}")

                # Score format may differ
                score = result.get('score', result.get('similarity', 0))
                context_parts.append(f"   Similarity Score: {score:.3f}")

            return "\n".join(context_parts)

        except Exception as e:
            logger.warning(f"Failed to retrieve similar templates: {e}", exc_info=True)
            return ""

    def _generate_template_with_llm(self, question: str) -> str:
        """
        Generate Nuclei template using LLM with RAG support

        Args:
            question: User's request for template generation

        Returns:
            Generated Nuclei template as YAML string
        """
        try:
            llm = self.llm_manager.get_llm()

            # Retrieve similar templates using RAG
            rag_context = self._retrieve_similar_templates(question, k=3)

            # Get prompt from prompts module with RAG context
            if rag_context:
                enhanced_question = f"{question}\n\n{rag_context}"
            else:
                enhanced_question = question

            prompt = NucleiGenerationPrompts.get_nuclei_template_generation_prompt(
                question=enhanced_question
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
