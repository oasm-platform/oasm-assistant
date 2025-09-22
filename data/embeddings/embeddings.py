import threading
from .models import (
    BaseEmbedding,
    OpenAIEmbedding,
    GoogleEmbedding,
    MistralEmbedding,
    SentenceTransformerEmbedding,
)
from common.logger import logger
from common.config import EmbeddingConfigs
from typing import List, Type
"""
Usage example:

from .embeddings import Embeddings

# Create an OpenAI embedding instance
embedding = Embeddings.create_embedding('openai', api_key='your_api_key', model_name='text-embedding-3-small')

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
    }
    
    _lock = threading.RLock()

    @classmethod
    def _normalize_provider(cls, provider: str) -> str:
        p = provider.lower().strip()
        return p

    @classmethod
    def _create_embedding_settings(cls, **kwargs) -> EmbeddingConfigs:
        """Create EmbeddingConfigs from kwargs"""
        print(f"_create_embedding_settings received kwargs: {kwargs}")
        # Map common parameter names to EmbeddingConfigs fields (using aliases)
        settings_kwargs = {}
        
        # Handle model name variations with defaults
        if 'model_name' in kwargs:
            settings_kwargs['EMBEDDING_MODEL_NAME'] = kwargs['model_name']
        elif 'model' in kwargs:
            settings_kwargs['EMBEDDING_MODEL_NAME'] = kwargs['model']
        elif 'name' in kwargs:
            settings_kwargs['EMBEDDING_MODEL_NAME'] = kwargs['name']
        else:
            # Set default model name if none provided
            settings_kwargs['EMBEDDING_MODEL_NAME'] = "all-MiniLM-L6-v2"
            
        # Handle API key variations
        if 'api_key' in kwargs:
            settings_kwargs['EMBEDDING_API_KEY'] = kwargs['api_key']
            
        # Handle other common settings
        if 'dimensions' in kwargs:
            settings_kwargs['EMBEDDING_DIMENSIONS'] = kwargs['dimensions']

        if 'base_url' in kwargs:
            settings_kwargs['EMBEDDING_BASE_URL'] = kwargs['base_url']
        
        print(f"Final settings_kwargs: {settings_kwargs}")
        
        # Create EmbeddingConfigs with explicit values to override env vars
        # Use _env_file=None to prevent reading from .env file
        result = EmbeddingConfigs(_env_file=None, **settings_kwargs)
        print(f"Created EmbeddingConfigs: model_name='{result.model_name}'")
        return result
    
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
        
        try:
            # Create EmbeddingConfigs from kwargs
            embedding_settings = cls._create_embedding_settings(**kwargs)
            # All embedding classes now expect EmbeddingConfigs as first argument
            instance = embedding_class(embedding_settings)
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
