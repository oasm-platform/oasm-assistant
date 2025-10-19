from typing import List, Union
from common.config.configs import EmbeddingConfigs


class BaseEmbedding:
    """
    Base class for all embedding models.

    All subclasses should:
    1. Accept EmbeddingConfigs in __init__
    2. Implement encode() method
    3. Implement dim property for embedding dimensions
    """

    def __init__(self, embedding_settings: EmbeddingConfigs):
        """
        Initialize base embedding model.

        Args:
            embedding_settings: Configuration for embedding model
        """
        super().__init__()
        self.embedding_settings = embedding_settings
        self.name = embedding_settings.model_name

    def encode(self, docs: Union[List[str], str]) -> Union[List[List[float]], List[float]]:
        """
        Encode text(s) into embeddings.

        Args:
            docs: Single string or list of strings to encode

        Returns:
            Single embedding vector or list of embedding vectors
        """
        raise NotImplementedError("The encode method must be implemented by subclasses")

    @property
    def dim(self) -> int:
        """
        Get embedding dimension.

        Returns:
            Dimension of embedding vectors
        """
        raise NotImplementedError("The dim property must be implemented by subclasses")


class APIBaseEmbedding(BaseEmbedding):
    """
    Base class for API-based embedding models (OpenAI, Google, Mistral, etc.)

    Adds API-specific attributes like api_key and base_url.
    """

    def __init__(self, embedding_settings: EmbeddingConfigs):
        """
        Initialize API-based embedding model.

        Args:
            embedding_settings: Configuration including API credentials
        """
        super().__init__(embedding_settings)
        self.api_key = embedding_settings.api_key
        self.base_url = embedding_settings.base_url

    def encode(self, docs: Union[List[str], str]) -> Union[List[List[float]], List[float]]:
        """API embeddings must implement encode()"""
        raise NotImplementedError("API embedding must implement encode()")

    @property
    def dim(self) -> int:
        """API embeddings must implement dim property"""
        raise NotImplementedError("API embedding must implement dim property")