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
        # OPTIMIZED WEIGHTS for Nuclei template generation:
        # - Vector search (0.7) is MORE important for semantic similarity
        #   (e.g., "SQL injection" should match templates about database attacks)
        # - Keyword search (0.3) helps with exact CVE IDs, specific tech names
        self.hybrid_retriever = HybridRetriever(
            vector_store=self.vector_store,
            config=configs.embedding,
            similarity_searcher=self.similarity_searcher,
            keyword_weight=0.3,  # For exact matches (CVE IDs, product names)
            vector_weight=0.7    # For semantic similarity (vulnerability types)
        )

        logger.info("NucleiTemplateService initialized with RAG support")

    def _retrieve_similar_templates(self, question: str, k: int = 5, similarity_threshold: float = 0.55) -> str:
        """
        Retrieve similar templates from database using RAG with quality filtering

        Args:
            question: User's request
            k: Number of similar templates to retrieve
            similarity_threshold: Minimum similarity score (0-1). Only templates above this are included.

        Returns:
            Formatted context string with similar templates
        """
        try:
            # Retrieve more candidates than needed for filtering
            candidates_k = min(k * 3, 15)  # Get 3x candidates for filtering, max 15

            # Try hybrid search first (requires tsv column)
            try:
                results = self.hybrid_retriever.hybrid_search(
                    table="nuclei_templates",
                    qtext=question,
                    k=candidates_k,
                    id_col="template_id",
                    title_col="name",
                    content_col="description",
                    embedding_col="embedding",
                    tsv_col="tsv",
                    meta_cols=["template", "tags"],  # Include template content and tags
                    candidates_each=100  # Increase candidate pool for better results
                )
            except Exception as hybrid_error:
                # Fallback to vector-only search if tsv column doesn't exist
                logger.debug(f"Hybrid search failed, using vector-only search: {hybrid_error}")
                results = self.hybrid_retriever.similarity_searcher.search(
                    table="nuclei_templates",
                    query=question,
                    k=candidates_k,
                    column="embedding",
                    id_col="template_id",
                    meta_cols=["name", "description", "template", "tags"]  # Include template content and tags
                )

            if not results:
                logger.info("No similar templates found in database")
                return ""

            # Filter by similarity threshold to ensure quality
            filtered_results = [
                r for r in results
                if r.get('score', r.get('similarity', 0)) >= similarity_threshold
            ]

            if not filtered_results:
                logger.info(f"No templates above similarity threshold {similarity_threshold}")
                return ""

            # Take top k after filtering
            top_results = filtered_results[:k]

            logger.info(f"Retrieved {len(top_results)} high-quality templates (threshold: {similarity_threshold})")

            # Format retrieved templates as clean context for LLM
            context_parts = []
            for idx, result in enumerate(top_results, 1):
                # Handle both hybrid search and vector search result formats
                metadata = result.get('metadata', {})
                name = metadata.get('title') or metadata.get('name', 'Unknown')
                description = metadata.get('content') or metadata.get('description', '')
                template_content = metadata.get('template', '')
                tags = metadata.get('tags', '')

                score = result.get('score', result.get('similarity', 0))

                # Build clean context entry
                context_parts.append(f"--- Reference Template {idx} ---")
                context_parts.append(f"Name: {name}")
                if description:
                    context_parts.append(f"Description: {description}")
                if tags:
                    context_parts.append(f"Tags: {tags}")
                context_parts.append(f"Relevance: {score:.2%}")  # Show as percentage

                # Add actual template YAML (most important part)
                if template_content:
                    context_parts.append(f"\nTemplate YAML:\n{template_content}")

                context_parts.append("")  # Empty line separator

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
            # k=3 is optimal (not too many to confuse, not too few to lack context)
            # threshold=0.55 ensures only relevant templates are included
            rag_context = self._retrieve_similar_templates(
                question=question,
                k=3,
                similarity_threshold=0.55
            )

            # Debug logging (visible in service logs)
            if rag_context:
                logger.info(f"RAG: Found {len([l for l in rag_context.split('---') if l.strip()])} relevant templates")
                print("=" * 80)
                print("RAG CONTEXT BEING SENT TO LLM:")
                print("=" * 80)
                print(rag_context[:500] + "..." if len(rag_context) > 500 else rag_context)
                print("=" * 80)
            else:
                logger.info("RAG: No relevant templates found, generating from base knowledge")
                print("No RAG context - generating template from LLM base knowledge only")

            # Pass RAG context directly to prompt (NEW: proper parameter)
            prompt = NucleiGenerationPrompts.get_nuclei_template_generation_prompt(
                question=question,
                rag_context=rag_context  # Properly structured now
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

            logger.info(f"Successfully generated template (length: {len(template)} chars)")

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
