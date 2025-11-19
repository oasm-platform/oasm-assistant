from .embedding_manager import EmbeddingManager
from common.config import configs
# Initialize Embeddings manager with settings (Singleton)
embeddings_manager = EmbeddingManager(config=configs.embedding)

__all__ = ['embeddings_manager', 'EmbeddingManager']
