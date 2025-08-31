from typing import List
# data/embeddings/embeddings.py
from __future__ import annotations
from typing import List, Dict, Tuple, Callable, Type, Any
from .models import (
    BaseEmbedding,
    EmbeddingConfig,
    OpenAIEmbedding,
    GoogleEmbedding,
    MistralEmbedding,
    SentenceTransformerEmbedding,
)
"""
Usage example:

from .embeddings import Embeddings

# Create an OpenAI embedding instance
embedding = Embeddings.create_embedding('openai', api_key='your_api_key')

# Get list of available providers
providers = Embeddings.get_available_providers()
"""

class Embeddings:
    """Factory & helpers for embedding providers."""

    # Provider chuẩn
    _providers: Dict[str, Type[BaseEmbedding]] = {
        "openai": OpenAIEmbedding,
        "google": GoogleEmbedding,
        "mistral": MistralEmbedding,
        "sentence_transformer": SentenceTransformerEmbedding,
    }

    # Alias thường gặp
    _ALIASES: Dict[str, str] = {
        "huggingface": "sentence_transformer",
        "hf": "sentence_transformer",
        "st": "sentence_transformer",
        "sentence-transformer": "sentence_transformer",
        "sentence-transformers": "sentence_transformer",
        "google-ai": "google",
    }

    # Cache instance theo (provider + model/config) để tránh khởi tạo lại tốn thời gian/RAM
    _CACHE: Dict[str, BaseEmbedding] = {}


    @classmethod
    def create_embedding(cls, provider: str, **kwargs: Any) -> BaseEmbedding:
        """
        Create an embedding instance based on the provider.

        Example:
            Embeddings.create_embedding("openai", api_key="...", model="text-embedding-3-small")
            Embeddings.create_embedding("sentence_transformer", name="all-MiniLM-L6-v2")
        """
        prov = cls._normalize_provider(provider)
        if prov not in cls._providers:
            raise ValueError(f"Unsupported embedding provider: {provider}. "
                             f"Available: {', '.join(sorted(cls._providers))}")

        # Chuẩn hoá kwargs cho SentenceTransformerEmbedding
        if cls._providers[prov] is SentenceTransformerEmbedding:
            if "config" not in kwargs:
                # chấp nhận name/model đều được
                model_name = kwargs.pop("name", kwargs.pop("model", "all-MiniLM-L6-v2"))
                kwargs["config"] = EmbeddingConfig(name=model_name)

        # Dùng cache nếu đã khởi tạo cùng cấu hình
        key = cls._cache_key(prov, kwargs)
        if key in cls._CACHE:
            return cls._CACHE[key]

        try:
            inst = cls._providers[prov](**kwargs)
        except ImportError as e:
            raise ValueError(f"{prov} provider is missing optional dependencies: {e}") from e
        except Exception as e:
            raise ValueError(f"Failed to create {prov} embedding: {e}") from e

        cls._CACHE[key] = inst
        return inst

    @classmethod
    def get_encoder(cls, provider: str, **kwargs: Any) -> Tuple[Callable[[List[str]], List[List[float]]], int, BaseEmbedding]:
        """
        Convenience: return (encode_fn, dimension, instance).
        Dùng trong indexer:
            encode, dim, _ = Embeddings.get_encoder("sentence_transformer", name="all-MiniLM-L6-v2")
            vecs = encode(list_of_texts)
        """
        emb = cls.create_embedding(provider, **kwargs)
        return emb.encode, emb.dim, emb

    @classmethod
    def from_settings(cls, settings) -> BaseEmbedding:
        """
        Create from project settings:
          settings.EMBEDDING_BACKEND (e.g., 'openai'|'sentence_transformer')
          settings.EMBEDDING_MODEL   (e.g., 'all-MiniLM-L6-v2'|'text-embedding-3-small')
          settings.EMBEDDING_API_KEY (optional)
          settings.EMBEDDING_BASE_URL (optional)
        """
        prov = getattr(settings, "EMBEDDING_BACKEND", "sentence_transformer")
        model = getattr(settings, "EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        api_key = getattr(settings, "EMBEDDING_API_KEY", None)
        base_url = getattr(settings, "EMBEDDING_BASE_URL", None)

        kwargs: Dict[str, Any] = {"name": model}
        if api_key: kwargs["api_key"] = api_key
        if base_url: kwargs["base_url"] = base_url
        return cls.create_embedding(prov, **kwargs)

    @classmethod
    def get_available_providers(cls) -> List[str]:
        return sorted(cls._providers.keys())

    @classmethod
    def register_provider(cls, name: str, provider_class: Type[BaseEmbedding]) -> None:
        if not issubclass(provider_class, BaseEmbedding):
            raise ValueError("Provider class must inherit from BaseEmbedding")
        cls._providers[cls._normalize_provider(name)] = provider_class

    # ---------- helpers ----------
    @classmethod
    def _normalize_provider(cls, name: str) -> str:
        n = (name or "").lower().strip().replace("-", "_")
        return cls._ALIASES.get(n, n)

    @staticmethod
    def _cache_key(prov: str, kwargs: Dict[str, Any]) -> str:
        # chỉ lấy vài tham số quyết định đến model để tạo key cache
        safe = {k: kwargs.get(k) for k in ("config", "model", "name", "dim", "api_key", "base_url") if k in kwargs}
        cfg = safe.get("config")
        if isinstance(cfg, EmbeddingConfig):
            safe["name"] = getattr(cfg, "name", None)
            safe.pop("config", None)
        parts = [f"{k}={safe[k]}" for k in sorted(safe)]
        return f"{prov}|{'|'.join(parts)}"
