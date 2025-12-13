from langchain_core.messages import HumanMessage
from sqlalchemy import text
from common.logger import logger
from common.config import configs
from llms import llm_manager
from llms.prompts import NucleiGenerationPrompts
from data.retrieval import hybrid_search_engine
from data.database import postgres_db

class NucleiTemplateService:
    """Service for generating Nuclei security templates using LLM with RAG"""

    def __init__(self):
        """Initialize the Nuclei template service"""
        self.llm_manager = llm_manager

        # Initialize Hybrid Search Engine
        self.hybrid_search = hybrid_search_engine
        logger.debug("NucleiTemplateService initialized with singleton HybridSearchEngine")

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

        except Exception as e:
            logger.warning(f"Failed to initialize BM25 index: {e}. Keyword search will be unavailable.")

    def _retrieve_similar_templates(
        self,
        question: str,
        k: int = None,
        similarity_threshold: float = None
    ) -> str:
        """Retrieve similar templates from database using RAG with quality filtering"""
        try:
            # Use config values if not provided
            if k is None:
                k = configs.rag.top_k
            if similarity_threshold is None:
                similarity_threshold = configs.rag.similarity_threshold

            # Use hybrid search to get relevant templates
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
                context_parts.append(f"Relevance: {score:.2%}")

                # Add actual template YAML (most important part)
                if template_content:
                    context_parts.append(f"\nTemplate YAML:\n{template_content}")

                context_parts.append("")

            return "\n".join(context_parts)

        except Exception as e:
            logger.warning(f"Failed to retrieve similar templates: {e}", exc_info=True)
            return ""

    async def generate_template(self, question: str) -> str:
        """Generate Nuclei template using LLM with RAG support"""
        try:
            llm = self.llm_manager.get_llm()

            # Retrieve similar templates using RAG
            rag_context = self._retrieve_similar_templates(question=question)

            # Pass RAG context directly to prompt
            prompt = NucleiGenerationPrompts.get_nuclei_template_generation_prompt(
                question=question,
                rag_context=rag_context
            )

            # Invoke LLM to generate template
            response = await llm.ainvoke([HumanMessage(content=prompt)])

            # Extract template from response
            template = response.content.strip()

            # Clean up markdown code blocks if present
            if template.startswith("```yaml"):
                template = template[7:]
            elif template.startswith("```"):
                template = template[3:]

            if template.endswith("```"):
                template = template[:-3]

            template = template.strip()

            logger.info(f"Successfully generated template (length: {len(template)} chars)")

            return template

        except Exception as e:
            logger.error(f"Error generating Nuclei template: {e}")
            raise
