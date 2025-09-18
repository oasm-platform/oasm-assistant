from __future__ import annotations
from .models import *
from typing import List

import threading
from common.logger import logger
from typing import Dict, List, Mapping, Optional, Type, Tuple, Any
"""
Usage example:

from .embeddings import Embeddings

# Create an OpenAI embedding instance
embedding = Embeddings.create_embedding('openai', api_key='your_api_key')

# Get list of available providers
providers = Embeddings.get_available_providers()
"""
def _freeze_value(v: Any):
    """Chuyển mọi giá trị sang dạng hashable ổn định (phục vụ cache key)."""
    if isinstance(v, dict):
        return tuple(sorted((k, _freeze_value(val)) for k, val in v.items()))
    if isinstance(v, (list, tuple, set)):
        return tuple(_freeze_value(x) for x in v)
    # Các kiểu nguyên thủy thì giữ nguyên; còn lại fallback sang repr
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return repr(v)


def _freeze_kwargs(kwargs: Dict[str, Any]) -> Tuple[Tuple[str, Any], ...]:
    """Đóng băng kwargs (đã chuẩn hóa) -> tuple sorted các (key, frozen_value)."""
    return tuple(sorted((k, _freeze_value(v)) for k, v in kwargs.items()))

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
    _cache: Dict[Tuple[str, Tuple[Tuple[str, Any], ...]], BaseEmbedding] = {}

    @classmethod
    def _normalize_provider(cls, provider: str) -> str:
        p = provider.lower().strip()
        if p == 'huggingface':  # alias
            p = 'sentence_transformer'
        return p

    @classmethod
    def _coerce_config(cls, embedding_class: Type[BaseEmbedding], kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Cho phép truyền tắt: name/model/device -> EmbeddingConfig (đặc biệt cho SentenceTransformer)."""
        if embedding_class == SentenceTransformerEmbedding and 'config' not in kwargs:
            cfg = {}
            if 'name' in kwargs:   cfg['name'] = kwargs.pop('name')
            if 'model' in kwargs:  cfg['name'] = kwargs.pop('model')
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
        provider = provider.lower().strip()
        provider = cls._normalize_provider(provider)
        logger.debug(f"[Embeddings] Request to create provider='{provider}' kwargs={kwargs}")
        
        if provider not in cls._providers:
            available_providers = ', '.join(cls._providers.keys())
            logger.error(f"[Embeddings] Unsupported provider '{provider}'. Available: {available_providers}")
            raise ValueError(
                f"Unsupported embedding provider: {provider}. "
                f"Available providers: {available_providers}"
            )
        
        embedding_class = cls._providers[provider]
        kwargs = cls._coerce_config(embedding_class, kwargs)

         # ---- CACHE KEY (provider, frozen_kwargs) ----
        frozen = _freeze_kwargs(kwargs)
        cache_key = (provider, frozen)
        
        with cls._lock:
            inst = cls._cache.get(cache_key)
            if inst is not None:
                logger.debug(f"[Embeddings] Cache hit provider={provider} kwargs={kwargs}")
                return inst

        logger.debug(f"[Embeddings] Cache miss -> creating provider={provider} kwargs={kwargs}")
        
        # Handle special case for SentenceTransformerEmbedding which requires EmbeddingConfig
        if embedding_class == SentenceTransformerEmbedding:
            if 'config' not in kwargs and 'name' in kwargs:
                kwargs['config'] = EmbeddingConfig(name=kwargs.pop('name'))
                logger.debug(f"[Embeddings] Auto-wrapped 'name' into EmbeddingConfig for {provider}")

        
        try:
            instance = embedding_class(**kwargs)
            with cls._lock:
                cls._cache[cache_key] = instance
                logger.info(f"[Embeddings] Created & cached instance: provider={provider}, class={embedding_class.__name__}")
            return instance
            return embedding_class(**kwargs)
        except Exception as e:
            logger.exception(f"[Embeddings] Failed to create {provider} embedding")
            raise ValueError(f"Failed to create {provider} embedding: {e}") from e

    
    @classmethod
    def get_available_providers(cls) -> List[str]:
        """Get list of available embedding providers"""
        providers = list(cls._providers.keys())
        logger.debug(f"[Embeddings] Available providers: {providers}")
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
            logger.error(f"[Embeddings] Tried to register invalid provider '{name}'")
            raise ValueError("Provider class must inherit from BaseEmbedding")
        
        cls._providers[name.lower()] = provider_class
        with cls._lock:
            cls._providers[name.lower()] = provider_class
        logger.info(f"[Embeddings] Registered new provider: {name} -> {provider_class.__name__}")

    @classmethod
    def clear_cache(cls, provider: str | None = None) -> int:
        """
        Xóa cache.
        - provider=None: xóa toàn bộ
        - provider='hf'/...: xóa cache của provider đó (chấp nhận alias 'huggingface')
        Returns: số entry đã xóa.
        """
        with cls._lock:
            if provider is None:
                n = len(cls._cache)
                cls._cache.clear()
                logger.info(f"[Embeddings] Cleared cache: {n} entries")
                return n

            p = cls._normalize_provider(provider)
            keys = [k for k in cls._cache.keys() if k[0] == p]
            for k in keys:
                cls._cache.pop(k, None)
            logger.info(f"[Embeddings] Cleared cache for provider={p}: {len(keys)} entries")
            return len(keys)