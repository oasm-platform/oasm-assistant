from langchain_core.messages import HumanMessage
from common.logger import logger
from common.config import configs
from llms import llm_manager
from app.protos import assistant_pb2, assistant_pb2_grpc
import grpc
from llms.prompts import NucleiGenerationPrompts
from data.retrieval import HybridSearchEngine
from data.database import postgres_db
from sqlalchemy import text


class NucleiTemplateService(assistant_pb2_grpc.NucleiTemplateServiceServicer):
    """Service for generating Nuclei security templates using LLM with RAG"""

    def __init__(self):
        """Initialize the Nuclei template service"""
        self.llm_manager = llm_manager

        # Initialize RAG components
        embed_dim = configs.embedding.dimensions or 384  # Default to 384 if not set
        self.hybrid_search = HybridSearchEngine(
            table_name=configs.rag.table_name,
            embedding_model_name=configs.embedding.model_name,
            vector_weight=configs.rag.vector_weight,
            keyword_weight=configs.rag.keyword_weight,
            embed_dim=embed_dim
        )

        # Load documents from database for BM25 indexing
        self._initialize_bm25_index()

        logger.info("NucleiTemplateService initialized with HybridSearchEngine")

    def _initialize_bm25_index(self):
        """Load documents from database and build BM25 index"""
        try:
            # Fetch all templates from database
            with postgres_db.get_session() as session:
                result = session.execute(text("""
                    SELECT template_id, name, description, template
                    FROM nuclei_templates
                """))
                rows = result.fetchall()

            if not rows:
                logger.warning("No templates found in database for BM25 indexing")
                return

            # Format documents for indexing
            documents = []
            for row in rows:
                template_id, name, description, template = row

                # Combine text fields for full-text search
                text_parts = [
                    name or '',
                    description or ''
                ]
                combined_text = ' '.join([p for p in text_parts if p])

                documents.append({
                    'text': combined_text,
                    'metadata': {
                        'id': template_id,
                        'name': name,
                        'description': description,
                        'template': template
                    }
                })

            # Index documents into BM25
            self.hybrid_search.keyword_retriever.index_documents(documents)
            logger.info(f"BM25 index initialized with {len(documents)} templates")

        except Exception as e:
            logger.warning(f"Failed to initialize BM25 index: {e}. Keyword search will be unavailable.")

    def _retrieve_similar_templates(
        self,
        question: str,
        k: int = None,
        similarity_threshold: float = None
    ) -> str:
        """
        Retrieve similar templates from database using RAG with quality filtering

        Args:
            question: User's request
            k: Number of similar templates to retrieve (default from config)
            similarity_threshold: Minimum similarity score (0-1). Only templates above this are included (default from config)

        Returns:
            Formatted context string with similar templates
        """
        try:
            # Use config values if not provided
            if k is None:
                k = configs.rag.top_k
            if similarity_threshold is None:
                similarity_threshold = configs.rag.similarity_threshold

            # Use hybrid search to get relevant templates
            # Get more candidates for filtering
            candidates_k = min(
                k * configs.rag.candidates_multiplier,
                configs.rag.max_candidates
            )

            results = self.hybrid_search.search(
                query=question,
                k=candidates_k,
                vector_k=configs.rag.vector_k,
                keyword_k=configs.rag.keyword_k,
                min_score=configs.rag.min_score
            )

            if not results:
                logger.info("No similar templates found in database")
                return ""

            # Filter by similarity threshold to ensure quality
            filtered_results = [
                r for r in results
                if r.get('score', 0) >= similarity_threshold
            ]

            if not filtered_results:
                logger.info(f"No templates above similarity threshold {similarity_threshold}")
                return ""

            # Take top k after filtering
            top_results = filtered_results[:k]

            # Format retrieved templates as clean context for LLM
            context_parts = []
            for idx, result in enumerate(top_results, 1):
                metadata = result.get('metadata', {})
                name = metadata.get('name', 'Unknown')
                description = metadata.get('description', '')
                template_content = metadata.get('template', '')
                score = result.get('score', 0)

                # Build clean context entry
                context_parts.append(f"--- Reference Template {idx} ---")
                context_parts.append(f"Name: {name}")
                if description:
                    context_parts.append(f"Description: {description}")
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
            # Use config values for k and similarity_threshold
            rag_context = self._retrieve_similar_templates(
                question=question
                # k and similarity_threshold will use config defaults
            )


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
