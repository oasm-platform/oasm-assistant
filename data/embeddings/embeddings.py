from .models import *
from typing import List

"""
Usage example:

from .embeddings import Embeddings

# Create an OpenAI embedding instance
embedding = Embeddings.create_embedding('openai', api_key='your_api_key')

# Get list of available providers
providers = Embeddings.get_available_providers()
"""

class Embeddings:
    """Embedding usage pattern factory class"""
    
    _providers = {
        'openai': OpenAIEmbedding,
        'google': GoogleEmbedding,
        'mistral': MistralEmbedding,
        'sentence_transformer': SentenceTransformerEmbedding,
        'huggingface': SentenceTransformerEmbedding,  # alias for sentence_transformer
    }
    
    @classmethod
    def create_embedding(cls, provider: str, **kwargs) -> BaseEmbedding:
        """
        Create an embedding instance based on the provider
        
        Args:
            provider: The embedding provider ('openai', 'google', 'mistral', 'sentence_transformer')
            **kwargs: Arguments specific to each embedding provider
        
        Returns:
            BaseEmbedding: An instance of the specified embedding provider
        
        Raises:
            ValueError: If the provider is not supported
        """
        provider = provider.lower().strip()
        
        if provider not in cls._providers:
            available_providers = ', '.join(cls._providers.keys())
            raise ValueError(
                f"Unsupported embedding provider: {provider}. "
                f"Available providers: {available_providers}"
            )
        
        embedding_class = cls._providers[provider]
        
        # Handle special case for SentenceTransformerEmbedding which requires EmbeddingConfig
        if embedding_class == SentenceTransformerEmbedding:
            if 'config' not in kwargs and 'name' in kwargs:
                kwargs['config'] = EmbeddingConfig(name=kwargs.pop('name'))
        
        try:
            return embedding_class(**kwargs)
        except Exception as e:
            raise ValueError(f"Failed to create {provider} embedding: {e}") from e
    
    @classmethod
    def get_available_providers(cls) -> List[str]:
        """Get list of available embedding providers"""
        return list(cls._providers.keys())
    
    @classmethod
    def register_provider(cls, name: str, provider_class: type):
        """
        Register a new embedding provider
        
        Args:
            name: Provider name
            provider_class: Class that inherits from BaseEmbedding
        """
        if not issubclass(provider_class, BaseEmbedding):
            raise ValueError("Provider class must inherit from BaseEmbedding")
        
        cls._providers[name.lower()] = provider_class