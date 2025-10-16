"""
Query processing engine for RAG system
"""
from typing import List, Tuple, Dict, Any, Optional, Union
from data.retrieval.similarity_searcher import SimilaritySearcher
from data.retrieval.hybrid_retriever import HybridRetriever
from data.retrieval.context_retriever import ContextRetriever
from data.retrieval.filter_engine import FilterEngine
from data.indexing.vector_store import PgVectorStore
from data.embeddings.embeddings import Embeddings
from common.logger import logger
import re
from data.database import postgres_db as db
from sqlalchemy import text


class QueryEngine:
    """
    Query processing engine that handles query understanding, expansion,
    and routing to appropriate retrieval methods in the RAG system.
    """
    
    def __init__(
        self,
        vector_store: Optional[PgVectorStore] = None,
        embedding_model: Optional[Any] = None,
        similarity_searcher: Optional[SimilaritySearcher] = None,
        hybrid_retriever: Optional[HybridRetriever] = None,
        context_retriever: Optional[ContextRetriever] = None,
        filter_engine: Optional[FilterEngine] = None
    ):
        """
        Initialize the query engine.
        
        Args:
            vector_store: PgVectorStore instance for database operations
            embedding_model: Embedding model for generating query vectors
            similarity_searcher: Pre-configured SimilaritySearcher instance
            hybrid_retriever: Pre-configured HybridRetriever instance
            context_retriever: Pre-configured ContextRetriever instance
            filter_engine: Pre-configured FilterEngine instance
        """
        self.vector_store = vector_store or PgVectorStore()
        self.embedding_model = embedding_model or Embeddings.create_embedding('sentence_transformer')
        self.similarity_searcher = similarity_searcher or SimilaritySearcher(
            vector_store=self.vector_store,
            embedding_model=self.embedding_model
        )
        self.hybrid_retriever = hybrid_retriever or HybridRetriever(
            vector_store=self.vector_store,
            embedding_model=self.embedding_model
        )
        self.context_retriever = context_retriever or ContextRetriever(
            vector_store=self.vector_store,
            embedding_model=self.embedding_model
        )
        self.filter_engine = filter_engine or FilterEngine(
            vector_store=self.vector_store,
            embedding_model=self.embedding_model
        )
        
        # Query type patterns for classification
        self.query_patterns = {
            'question': [
                r'\b(what|how|why|when|where|who|which|whose|whom)\b',
                r'\?$' # Ends with question mark
            ],
            'instruction': [
                r'\b(please|could you|would you|help me|tell me|explain|describe|summarize|find|search|look for)\b'
            ],
            'command': [
                r'\b(show|display|list|get|retrieve|fetch|provide|give|analyze|check|verify|validate)\b'
            ]
        }
    
    def process_query(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        table_name: str = "text_vectors",
        k: int = 10,
        use_hybrid: bool = True,
        use_context: bool = True,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[float, Dict[str, Any]]]:
        """
        Process a query through the full pipeline: understanding, expansion, retrieval, filtering.
        
        Args:
            query: User query to process
            conversation_id: ID of the current conversation (for context)
            table_name: Name of the table to search in
            k: Number of results to return
            use_hybrid: Whether to use hybrid search (vector + keyword)
            use_context: Whether to use context-aware retrieval
            filters: Optional filters to apply to results
            
        Returns:
            List of (score, metadata) tuples with processed results
        """
        try:
            # Step 1: Understand and classify the query
            query_type = self.classify_query(query)
            logger.info(f"Query classified as: {query_type}")
            
            # Step 2: Expand the query based on type and context
            expanded_query = self.expand_query(query, query_type, conversation_id)
            
            # Step 3: Choose retrieval method based on query type and parameters
            if use_context:
                results = self.context_retriever.retrieve_with_context(
                    table_name=table_name,
                    query=expanded_query,
                    conversation_id=conversation_id,
                    k=k,
                    metadata_filters=filters
                )
            elif use_hybrid:
                results = self.hybrid_retriever.hybrid_search(
                    table_name=table_name,
                    query_text=expanded_query,
                    k=k
                )
            else:
                results = self.similarity_searcher.search_by_text(
                    table_name=table_name,
                    query_text=expanded_query,
                    k=k
                )
            
            # Step 4: Apply filters if provided
            if filters:
                results = self.filter_engine.apply_multiple_filters(
                    results,
                    metadata_filters=filters
                )
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return []
    
    def classify_query(self, query: str) -> str:
        """
        Classify the query type to determine the best processing approach.
        
        Args:
            query: Query string to classify
            
        Returns:
            Query type ('question', 'instruction', 'command', or 'other')
        """
        query_lower = query.lower().strip()
        
        for query_type, patterns in self.query_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    return query_type
        
        return 'other'
    
    def expand_query(self, query: str, query_type: str, conversation_id: Optional[str] = None) -> str:
        """
        Expand the query using various techniques based on query type.
        
        Args:
            query: Original query string
            query_type: Type of query ('question', 'instruction', 'command', 'other')
            conversation_id: ID of the current conversation (for context)
            
        Returns:
            Expanded query string
        """
        # Get conversation context if available
        context_text = ""
        if conversation_id:
            # For simplicity, we'll just get the last few messages
            # In a real implementation, we might call context_retriever._get_conversation_context
            try:
                with db.get_session() as session:
                    context_query = text("""
                        SELECT question, answer
                        FROM messages
                        WHERE conversation_id = :conversation_id
                        ORDER BY created_at DESC
                        LIMIT 3
                    """)
                    
                    result = session.execute(context_query, {"conversation_id": conversation_id})
                    context_messages = []
                    for row in result:
                        if row.question:
                            context_messages.append(f"Q: {row.question}")
                        if row.answer:
                            context_messages.append(f"A: {row.answer}")
                    
                    if context_messages:
                        context_text = " ".join(reversed(context_messages))
            except Exception as e:
                logger.warning(f"Could not retrieve conversation context: {e}")
        
        # Apply different expansion strategies based on query type
        if query_type == 'question':
            # For questions, we might want to expand with related concepts
            expanded_query = self._expand_question(query, context_text)
        elif query_type == 'instruction':
            # For instructions, focus on action and intent
            expanded_query = self._expand_instruction(query, context_text)
        elif query_type == 'command':
            # For commands, emphasize the action requested
            expanded_query = self._expand_command(query, context_text)
        else:
            # For other types, use general expansion
            expanded_query = self._expand_general(query, context_text)
        
        return expanded_query
    
    def _expand_question(self, query: str, context: str = "") -> str:
        """
        Expand a question-type query.
        
        Args:
            query: Original question
            context: Conversation context
            
        Returns:
            Expanded question query
        """
        # Extract key terms and concepts
        key_terms = self._extract_key_terms(query)
        
        # For questions, we can expand by identifying the main concept being asked about
        expanded_query = f"{context} {query} {', '.join(key_terms)}".strip()
        return expanded_query
    
    def _expand_instruction(self, query: str, context: str = "") -> str:
        """
        Expand an instruction-type query.
        
        Args:
            query: Original instruction
            context: Conversation context
            
        Returns:
            Expanded instruction query
        """
        # Extract action and intent
        expanded_query = f"{context} {query}".strip()
        return expanded_query
    
    def _expand_command(self, query: str, context: str = "") -> str:
        """
        Expand a command-type query.
        
        Args:
            query: Original command
            context: Conversation context
            
        Returns:
            Expanded command query
        """
        # Emphasize the action requested
        expanded_query = f"{context} {query}".strip()
        return expanded_query
    
    def _expand_general(self, query: str, context: str = "") -> str:
        """
        Expand a general query.
        
        Args:
            query: Original query
            context: Conversation context
            
        Returns:
            Expanded general query
        """
        expanded_query = f"{context} {query}".strip()
        return expanded_query
    
    def _extract_key_terms(self, text: str) -> List[str]:
        """
        Extract key terms from text using simple heuristics.
        
        Args:
            text: Text to extract key terms from
            
        Returns:
            List of key terms
        """
        # Simple approach: extract capitalized words and words after question words
        words = text.split()
        key_terms = []
        
        question_words = {'what', 'how', 'why', 'when', 'where', 'who', 'which', 'whose', 'whom'}
        
        for i, word in enumerate(words):
            # Clean the word of punctuation
            clean_word = re.sub(r'[^\w\s]', '', word).strip()
            if clean_word:
                # Add capitalized words (potential proper nouns)
                if clean_word[0].isupper() and len(clean_word) > 2:
                    key_terms.append(clean_word)
                # Add words that follow question words
                if i > 0 and words[i-1].lower().rstrip('?,.!;:') in question_words:
                    key_terms.append(clean_word)
        
        return list(set(key_terms))  # Remove duplicates
    
    def query_by_vector(
        self,
        query_vector: List[float],
        table_name: str = "text_vectors",
        k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[float, Dict[str, Any]]]:
        """
        Query using a pre-computed vector.
        
        Args:
            query_vector: Pre-computed vector representation of the query
            table_name: Name of the table to search in
            k: Number of results to return
            filters: Optional filters to apply to results
            
        Returns:
            List of (score, metadata) tuples
        """
        try:
            # Perform similarity search
            results = self.similarity_searcher.search_by_vector(
                table_name=table_name,
                query_vector=query_vector,
                k=k
            )
            
            # Apply filters if provided
            if filters:
                # Convert similarity search results to the format expected by filter engine
                formatted_results = [(score, metadata) for _, score, metadata in results]
                filtered_results = self.filter_engine.apply_multiple_filters(
                    formatted_results,
                    metadata_filters=filters
                )
                return filtered_results
            
            # Convert to the expected format (score, metadata)
            return [(score, metadata) for _, score, metadata in results]
            
        except Exception as e:
            logger.error(f"Error in vector query: {e}")
            return []
    
    def batch_query(
        self,
        queries: List[str],
        table_name: str = "text_vectors",
        k: int = 5,
        use_hybrid: bool = True
    ) -> List[List[Tuple[float, Dict[str, Any]]]]:
        """
        Process multiple queries in batch.
        
        Args:
            queries: List of query strings to process
            table_name: Name of the table to search in
            k: Number of results to return per query
            use_hybrid: Whether to use hybrid search
            
        Returns:
            List of result lists, one for each query
        """
        batch_results = []
        
        for query in queries:
            if use_hybrid:
                results = self.hybrid_retriever.hybrid_search(
                    table_name=table_name,
                    query_text=query,
                    k=k
                )
            else:
                results = self.similarity_searcher.search_by_text(
                    table_name=table_name,
                    query_text=query,
                    k=k
                )
            batch_results.append(results)
        
        return batch_results
    
    def get_query_suggestions(
        self,
        partial_query: str,
        table_name: str = "text_vectors",
        k: int = 5
    ) -> List[str]:
        """
        Generate query suggestions based on partial input.
        
        Args:
            partial_query: Partial query string
            table_name: Name of the table to search in for suggestions
            k: Number of suggestions to return
            
        Returns:
            List of query suggestions
        """
        try:
            # This is a simplified implementation
            # In a real system, this might use a dedicated suggestions table
            # or a specialized model for query completion
            
            # For now, return a simple heuristic-based suggestion
            suggestions = []
            
            # Add the partial query itself as a base
            if partial_query.strip():
                suggestions.append(partial_query.strip())
            
            # Add some common expansions
            if partial_query.lower().startswith(('what', 'how', 'why')):
                suggestions.append(f"{partial_query} security")
                suggestions.append(f"{partial_query} vulnerability")
            elif partial_query.lower().startswith(('tell me', 'explain')):
                suggestions.append(f"{partial_query} about cybersecurity")
                suggestions.append(f"{partial_query} about threats")
            
            return suggestions[:k]
            
        except Exception as e:
            logger.error(f"Error generating query suggestions: {e}")
            return []