from langchain_core.messages import HumanMessage
from common.logger import logger
from common.config import configs
from llms import llm_manager
from app.protos import assistant_pb2, assistant_pb2_grpc
import grpc
from llms.prompts import NucleiGenerationPrompts
from data.retrieval import HybridSearchEngine
from data.database import postgres_db
from data.database.models.nuclei_templates import NucleiTemplates


class NucleiTemplateService(assistant_pb2_grpc.NucleiTemplateServiceServicer):
    """Service for generating Nuclei security templates using LLM with LlamaIndex RAG"""

    def __init__(self):
        """Initialize the Nuclei template service with LlamaIndex"""
        self.llm_manager = llm_manager
        self.db = postgres_db

        # Initialize LlamaIndex Hybrid Retriever with HNSW (semantic) + BM25 (keyword)
        # OPTIMIZED WEIGHTS for Nuclei template generation:
        # - Vector search (0.7) is MORE important for semantic similarity
        #   (e.g., "SQL injection" should match templates about database attacks)
        # - Keyword search (0.3) helps with exact CVE IDs, specific tech names
        self.search_engine = HybridSearchEngine(
            table_name="nuclei_templates",
            embedding_model_name=configs.embedding.model_name,
            vector_weight=0.7,  # Semantic similarity (HNSW)
            keyword_weight=0.3,  # Exact keyword matches (BM25)
            embed_dim=configs.embedding.dimensions or 384
        )

        # Load existing index from database
        try:
            self.search_engine.load_vector_index()
            self._load_bm25_index()
        except Exception as e:
            logger.warning(f"Failed to load existing index: {e}. Will create new index when needed.")

    def _load_bm25_index(self):
        """Load all documents from database to build BM25 index"""
        try:
            with self.db.get_session() as session:
                templates = session.query(NucleiTemplates).all()

                if not templates:
                    return

                # Convert to document format for BM25
                documents = []
                for template in templates:
                    # Combine name, description, and template content for better search
                    text = f"{template.name}\n{template.description or ''}\n{template.template or ''}"
                    metadata = {
                        'id': str(template.template_id),
                        'template_id': str(template.template_id),
                        'name': template.name,
                        'description': template.description or '',
                        'template': template.template or '',
                        'tags': getattr(template, 'tags', '')
                    }
                    documents.append({
                        'text': text,
                        'metadata': metadata
                    })

                # Build BM25 index using proper API
                self.search_engine.keyword_retriever.index_documents(documents)

        except Exception as e:
            logger.error(f"Failed to load BM25 index: {e}")

    def _retrieve_similar_templates(self, question: str, k: int = 5, similarity_threshold: float = 0.55) -> str:
        """
        Retrieve similar templates from database using hybrid search (vector + keyword) (HNSW + BM25)

        Args:
            question: User's request
            k: Number of similar templates to retrieve
            similarity_threshold: Minimum similarity score (0-1)

        Returns:
            Formatted context string with similar templates
        """
        try:
            # Use hybrid search (vector + keyword) (HNSW + BM25)
            results = self.search_engine.search(
                query=question,
                k=k,
                vector_k=50,  # Get more candidates for better results
                keyword_k=50,
                min_score=similarity_threshold
            )

            if not results:
                return ""

            # Format retrieved templates as clean context for LLM
            context_parts = []
            for idx, result in enumerate(results, 1):
                metadata = result.get('metadata', {})
                name = metadata.get('name', 'Unknown')
                description = metadata.get('description', '')
                template_content = metadata.get('template', '')
                tags = metadata.get('tags', '')

                score = result.get('score', 0)
                vector_score = result.get('vector_score', 0)
                keyword_score = result.get('keyword_score', 0)
                sources = result.get('sources', [])

                # Build clean context entry
                context_parts.append(f"--- Reference Template {idx} ---")
                context_parts.append(f"Name: {name}")
                if description:
                    context_parts.append(f"Description: {description}")
                if tags:
                    context_parts.append(f"Tags: {tags}")
                context_parts.append(f"Relevance: {score:.2%} (Vector: {vector_score:.2f}, Keyword: {keyword_score:.2f})")
                context_parts.append(f"Match Sources: {', '.join(sources)}")

                # Add actual template YAML (most important part)
                if template_content:
                    context_parts.append(f"\nTemplate YAML:\n{template_content}")

                context_parts.append("")  # Empty line separator

            return "\n".join(context_parts)

        except Exception as e:
            logger.error(f"Failed to retrieve similar templates: {e}")
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

            # Retrieve similar templates using hybrid search
            rag_context = self._retrieve_similar_templates(
                question=question,
                k=3,
                similarity_threshold=0.55
            )

            # Generate prompt with RAG context
            prompt = NucleiGenerationPrompts.get_nuclei_template_generation_prompt(
                question=question,
                rag_context=rag_context
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
