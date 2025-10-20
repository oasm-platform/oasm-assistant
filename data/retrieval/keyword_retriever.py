"""
Keyword-based retrieval using BM25 algorithm
"""
from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi
import numpy as np
from common.logger import logger


class KeywordRetriever:
    """
    BM25-based keyword retriever for exact term matching

    Use cases:
    - Exact keyword matches (CVE IDs, product names, etc.)
    - Technical term searches
    - Complement to semantic search
    """

    def __init__(self):
        """Initialize keyword retriever"""
        self.bm25_index: Optional[BM25Okapi] = None
        self.documents: List[str] = []
        self.metadata: List[Dict[str, Any]] = []
        logger.info("KeywordRetriever initialized")

    def index_documents(self, documents: List[Dict[str, Any]]) -> None:
        """
        Build BM25 index from documents

        Args:
            documents: List of dicts with keys:
                      - 'text': Document text content
                      - 'metadata': Document metadata (id, name, etc.)
        """
        try:
            logger.info(f"Building BM25 index for {len(documents)} documents...")

            self.documents = [doc.get('text', '') for doc in documents]
            self.metadata = [doc.get('metadata', {}) for doc in documents]

            # Tokenize documents (simple whitespace tokenization)
            tokenized_docs = [doc.lower().split() for doc in self.documents]

            # Build BM25 index
            self.bm25_index = BM25Okapi(tokenized_docs)

            logger.info(f"BM25 index built successfully with {len(documents)} documents")

        except Exception as e:
            logger.error(f"Failed to build BM25 index: {e}")
            raise

    def search(self, query: str, k: int = 10) -> List[Dict[str, Any]]:
        """
        Search for documents using BM25 keyword matching

        Args:
            query: Search query text
            k: Number of results to return

        Returns:
            List of results with format:
            [{
                'id': document_id,
                'text': document_text,
                'metadata': document_metadata,
                'score': bm25_score,
                'source': 'keyword'
            }]
        """
        try:
            if self.bm25_index is None:
                logger.warning("BM25 index not initialized. Please index documents first.")
                return []

            # Tokenize query
            tokenized_query = query.lower().split()

            # Get BM25 scores
            scores = self.bm25_index.get_scores(tokenized_query)

            # Get top k results
            top_k_indices = np.argsort(scores)[::-1][:k]

            results = []
            for idx in top_k_indices:
                if scores[idx] > 0:  # Only include results with positive scores
                    results.append({
                        'id': self.metadata[idx].get('id', str(idx)),
                        'text': self.documents[idx],
                        'metadata': self.metadata[idx],
                        'score': float(scores[idx]),
                        'source': 'keyword'
                    })

            logger.debug(f"Keyword search returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Keyword search failed: {e}")
            return []

    def is_ready(self) -> bool:
        """Check if index is ready for searching"""
        return self.bm25_index is not None

    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics"""
        return {
            'indexed_documents': len(self.documents),
            'is_ready': self.is_ready(),
            'index_type': 'BM25Okapi'
        }
