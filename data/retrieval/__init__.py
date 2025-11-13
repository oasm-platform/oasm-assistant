from .vector_retriever import VectorRetriever
from .keyword_retriever import KeywordRetriever
from .hybrid_search import HybridSearchEngine
from .score_utils import normalize_scores, combine_scores
from common.config import configs

# Initialize singleton instances with default configuration
hybrid_search_engine = HybridSearchEngine(
    table_name=configs.rag.table_name if hasattr(configs, 'rag') else "nuclei_templates",
    embedding_model_name=configs.embedding.model_name if hasattr(configs, 'embedding') else None,
    vector_weight=configs.rag.vector_weight if hasattr(configs, 'rag') else 0.7,
    keyword_weight=configs.rag.keyword_weight if hasattr(configs, 'rag') else 0.3,
    embed_dim=configs.embedding.dimensions if hasattr(configs, 'embedding') else 384,
)

__all__ = [
    "VectorRetriever",
    "KeywordRetriever",
    "HybridSearchEngine",
    "hybrid_search_engine",  # Singleton instance
    "normalize_scores",
    "combine_scores",
]
