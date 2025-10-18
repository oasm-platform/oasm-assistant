from .embeddings import Embeddings
from common.config import configs
from typing import Optional
import threading
from .models import BaseEmbedding

# Singleton instance
_embedding_model: Optional[BaseEmbedding] = None
_lock = threading.RLock()

def get_embedding_model():
    """
    Get or create the singleton embedding model instance.
    Uses lazy loading to avoid loading model at import time.
    Thread-safe singleton pattern.
    """
    global _embedding_model
    if _embedding_model is None:
        with _lock:
            # Double-check locking pattern
            if _embedding_model is None:
                # Use the factory method with config settings
                provider = configs.embedding.provider or 'sentence_transformer'
                _embedding_model = Embeddings.create_embedding(
                    provider=provider,
                    model_name=configs.embedding.model_name,
                    api_key=configs.embedding.api_key,
                    base_url=configs.embedding.base_url,
                    dimensions=configs.embedding.dimensions
                )
    return _embedding_model

# For backward compatibility
def __getattr__(name):
    if name == "embedding_model":
        return get_embedding_model()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = [
    "get_embedding_model",
    "embedding_model",  # backward compatibility
    "Embeddings",  # Export factory class as well
]
