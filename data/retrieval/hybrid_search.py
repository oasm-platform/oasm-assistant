"""
Hybrid search combining vector (semantic) and keyword (BM25) retrieval
"""
from typing import List, Dict, Any, Optional
from .vector_retriever import VectorRetriever
from .keyword_retriever import KeywordRetriever
from .score_utils import normalize_scores
from common.logger import logger
from common.config import configs


class HybridSearchEngine:
    """
    Hybrid search engine combining (Singleton):
    - Vector retrieval (HNSW) for semantic similarity
    - Keyword retrieval (BM25) for exact term matching

    Benefits:
    - Better recall (finds more relevant results)
    - Handles both semantic and lexical matching
    - Configurable weights for different use cases
    """

    _instance: Optional['HybridSearchEngine'] = None
    _initialized = False

    def __new__(
        cls,
        table_name: str = "nuclei_templates",
        embedding_model_name: Optional[str] = None,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
        embed_dim: int = 384,
    ):
        """
        Singleton implementation - ensures only one instance exists

        Args:
            table_name: PostgreSQL table name (only used on first instantiation)
            embedding_model_name: HuggingFace model (only used on first instantiation)
            vector_weight: Weight for semantic search (only used on first instantiation)
            keyword_weight: Weight for keyword search (only used on first instantiation)
            embed_dim: Embedding dimension (only used on first instantiation)
        """
        if cls._instance is None:
            cls._instance = super(HybridSearchEngine, cls).__new__(cls)
        return cls._instance

    def __init__(
        self,
        table_name: str = "nuclei_templates",
        embedding_model_name: Optional[str] = None,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
        embed_dim: int = 384,
    ):
        """
        Initialize hybrid search engine - only runs once due to Singleton

        Args:
            table_name: PostgreSQL table name
            embedding_model_name: HuggingFace embedding model
            vector_weight: Weight for semantic search (0-1)
            keyword_weight: Weight for keyword search (0-1)
            embed_dim: Embedding dimension
        """
        # Only initialize once
        if self._initialized:
            return

        self.table_name = table_name
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight

        # Validate weights
        total_weight = vector_weight + keyword_weight
        if abs(total_weight - 1.0) > 1e-6:
            logger.warning(
                f"Weights don't sum to 1.0 (vector={vector_weight}, keyword={keyword_weight}). "
                f"Results may be scaled differently."
            )

        # Initialize retrievers (singletons)
        self.vector_retriever = VectorRetriever(
            table_name=table_name,
            embedding_model_name=embedding_model_name,
            embed_dim=embed_dim
        )

        self.keyword_retriever = KeywordRetriever()

        # Mark as initialized
        HybridSearchEngine._initialized = True
        logger.debug(f"HybridSearchEngine singleton initialized (vector_weight={vector_weight}, keyword_weight={keyword_weight})")

    def load_vector_index(self) -> None:
        """Load existing vector index from database"""
        self.vector_retriever.load_index()

    def index_documents(self, documents: List[Dict[str, Any]]) -> None:
        """
        Index documents into both vector and keyword indexes

        Args:
            documents: List of dicts with keys:
                      - 'text': Document text
                      - 'metadata': Document metadata
        """
        logger.info(f"Indexing {len(documents)} documents into hybrid search...")

        # Index into vector store (HNSW)
        # Note: This is typically done separately via database migrations
        # self.vector_retriever.index_documents(documents)

        # Index into keyword store (BM25)
        self.keyword_retriever.index_documents(documents)

        logger.info("Hybrid indexing completed")

    def search(
        self,
        query: str,
        k: int = 10,
        vector_k: int = 50,
        keyword_k: int = 50,
        min_score: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining vector and keyword results

        Args:
            query: Search query text
            k: Final number of results to return
            vector_k: Number of candidates from vector search
            keyword_k: Number of candidates from keyword search
            min_score: Minimum combined score threshold

        Returns:
            List of top k results sorted by hybrid score
            [{
                'id': result_id,
                'text': result_text,
                'metadata': result_metadata,
                'score': hybrid_score,
                'vector_score': normalized_vector_score,
                'keyword_score': normalized_keyword_score,
                'sources': ['vector', 'keyword']  # which retrievers found this
            }]
        """
        try:
            logger.debug(f"Hybrid search for: '{query[:50]}...'")

            # Get candidates from both retrievers
            vector_results = self.vector_retriever.search(query, k=vector_k)
            keyword_results = self.keyword_retriever.search(query, k=keyword_k)

            logger.debug(
                f"Retrieved {len(vector_results)} vector results, "
                f"{len(keyword_results)} keyword results"
            )

            # Normalize scores for each retriever
            vector_scores = normalize_scores([r['score'] for r in vector_results])
            keyword_scores = normalize_scores([r['score'] for r in keyword_results])

            # Update normalized scores
            for i, result in enumerate(vector_results):
                result['normalized_score'] = vector_scores[i]
            for i, result in enumerate(keyword_results):
                result['normalized_score'] = keyword_scores[i]

            # Merge results by ID and compute hybrid score
            merged_results = {}

            for result in vector_results:
                result_id = result['id']
                merged_results[result_id] = {
                    'id': result_id,
                    'text': result['text'],
                    'metadata': result['metadata'],
                    'vector_score': result['normalized_score'],
                    'keyword_score': 0.0,
                    'sources': ['vector']
                }

            for result in keyword_results:
                result_id = result['id']
                if result_id in merged_results:
                    merged_results[result_id]['keyword_score'] = result['normalized_score']
                    merged_results[result_id]['sources'].append('keyword')
                else:
                    merged_results[result_id] = {
                        'id': result_id,
                        'text': result['text'],
                        'metadata': result['metadata'],
                        'vector_score': 0.0,
                        'keyword_score': result['normalized_score'],
                        'sources': ['keyword']
                    }

            # Calculate hybrid scores
            final_results = []
            for result_id, result in merged_results.items():
                hybrid_score = (
                    self.vector_weight * result['vector_score'] +
                    self.keyword_weight * result['keyword_score']
                )

                if hybrid_score >= min_score:
                    final_results.append({
                        'id': result_id,
                        'text': result['text'],
                        'metadata': result['metadata'],
                        'score': hybrid_score,
                        'vector_score': result['vector_score'],
                        'keyword_score': result['keyword_score'],
                        'sources': result['sources']
                    })

            # Sort by hybrid score (descending)
            final_results.sort(key=lambda x: x['score'], reverse=True)

            # Return top k
            top_results = final_results[:k]
            logger.debug(f"Hybrid search returned {len(top_results)} results")

            return top_results

        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            return []

    def is_ready(self) -> bool:
        """Check if both retrievers are ready"""
        return (
            self.vector_retriever.is_ready() and
            self.keyword_retriever.is_ready()
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for both retrievers"""
        return {
            'vector_retriever': self.vector_retriever.get_stats(),
            'keyword_retriever': self.keyword_retriever.get_stats(),
            'weights': {
                'vector': self.vector_weight,
                'keyword': self.keyword_weight
            },
            'is_ready': self.is_ready()
        }
