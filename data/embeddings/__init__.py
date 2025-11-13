from .embeddings import Embeddings
from common.config import configs
from .models import BaseEmbedding

# Initialize Embeddings manager with settings (Singleton)
embeddings_manager = Embeddings(config=configs.embedding)

# Backward compatibility helper function
def get_embedding_model() -> BaseEmbedding:
    """
    Get the singleton embedding model instance.
    This is a backward compatibility wrapper.

    Returns:
        BaseEmbedding: The singleton embedding model instance
    """
    return embeddings_manager.get_embedding()

__all__ = ['embeddings_manager', 'Embeddings', 'get_embedding_model']
