from __future__ import annotations

import threading
from .models import (
    BaseEmbedding,
    OpenAIEmbedding,
    GoogleEmbedding,
    MistralEmbedding,
    SentenceTransformerEmbedding,
    EmbeddingConfig,
)
from common.logger import logger
from typing import Dict, List, Type, Any
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
    
    _lock = threading.RLock()

    @classmethod
    def _normalize_provider(cls, provider: str) -> str:
        p = provider.lower().strip()
        if p == 'huggingface':  # alias
            p = 'sentence_transformer'
        return p

    @classmethod
    def _coerce_config(cls, embedding_class: Type[BaseEmbedding], kwargs: Dict[str, Any]) -> Dict[str, Any]:
        if embedding_class == SentenceTransformerEmbedding and 'config' not in kwargs:
            cfg = {}
            if 'name' in kwargs:   
                cfg['name'] = kwargs.pop('name')
            elif 'model' in kwargs:  
                cfg['name'] = kwargs.pop('model')
            if 'device' in kwargs: cfg['device'] = kwargs.pop('device')
            if cfg:
                kwargs['config'] = EmbeddingConfig(**cfg)
        return kwargs
    
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
        # provider = provider.lower().strip()
        provider = cls._normalize_provider(provider)
        
        if provider not in cls._providers:
            available_providers = ', '.join(cls._providers.keys())
            logger.error(f"[Embeddings] Unsupported provider '{provider}'. Available: {available_providers}")
            raise ValueError(
                f"Unsupported embedding provider: {provider}. "
                f"Available providers: {available_providers}"
            )
        
        embedding_class = cls._providers[provider]
        kwargs = cls._coerce_config(embedding_class, kwargs)
        
        try:
            instance = embedding_class(**kwargs)
            return instance
        except Exception as e:
            logger.exception(f"[Embeddings] Failed to create {provider} embedding")
            raise ValueError(f"Failed to create {provider} embedding: {e}") from e

    
    @classmethod
    def get_available_providers(cls) -> List[str]:
        """Get list of available embedding providers"""
        return list(cls._providers.keys())
    
    @classmethod
    def register_provider(cls, name: str, provider_class: Type[BaseEmbedding]):
        """
        Register a new embedding provider
        
        Args:
            name: Provider name
            provider_class: Class that inherits from BaseEmbedding
        """
        if not issubclass(provider_class, BaseEmbedding):
            logger.error(f"[Embeddings] Tried to register invalid provider '{name}'")
            raise ValueError("Provider class must inherit from BaseEmbedding")
        
        with cls._lock:
            cls._providers[name.lower()] = provider_class
