"""
Embedding Provider Factory/Registry

- Purpose: Central place to create embedding providers by name.
- Features:
  * Typed provider registry with alias resolution
  * Provider-specific kwargs normalization (e.g., SentenceTransformer config)
  * Safe registration API with validation
  * Helpful errors and logging
"""

from __future__ import annotations

from common.logger import logger
from typing import Dict, List, Mapping, Optional, Type, Tuple

from .models import (
    BaseEmbedding,
    EmbeddingConfig,
    OpenAIEmbedding,
    GoogleEmbedding,
    MistralEmbedding,
    SentenceTransformerEmbedding,
)

class Embeddings:
    """Factory/Registry for embedding providers."""

    # Canonical providers
    _providers: Dict[str, Type[BaseEmbedding]] = {
        "openai": OpenAIEmbedding,
        "google": GoogleEmbedding,
        "mistral": MistralEmbedding,
        "sentence_transformer": SentenceTransformerEmbedding,
    }

    # Aliases → canonical names
    _aliases: Dict[str, str] = {
        "huggingface": "sentence_transformer",
        "sentence-transformer": "sentence_transformer",
        "hf": "sentence_transformer",
        "oa": "openai",
        "gcp": "google",
    }

    @classmethod
    def create_embedding(cls, provider: str, **kwargs) -> BaseEmbedding:
        """
        Create an embedding instance based on provider name.

        Args:
            provider: One of: 'openai', 'google', 'mistral', 'sentence_transformer'
                      (aliases supported, e.g., 'huggingface' → 'sentence_transformer')
            **kwargs: Provider-specific constructor arguments.

        Returns:
            BaseEmbedding: a configured embedding instance.

        Raises:
            ValueError: if provider is unsupported or constructor fails.
        """
        name = cls._normalize_name(provider)

        embedding_cls = cls._providers.get(name)
        if embedding_cls is None:
            available = ", ".join(sorted(cls._providers.keys()))
            raise ValueError(
                f"Unsupported embedding provider: {provider!r}. "
                f"Available providers: {available}"
            )

        # Normalize kwargs per provider (e.g., config for SentenceTransformer)
        kwargs = cls._normalize_kwargs(name, kwargs)

        try:
            instance = embedding_cls(**kwargs)
            logger.debug("Created embedding provider %s with kwargs=%r", name, kwargs)
            return instance
        except Exception as e:
            raise ValueError(f"Failed to create {name} embedding: {e}") from e

    @classmethod
    def get_available_providers(cls) -> List[str]:
        """List canonical provider names (aliases not included)."""
        return sorted(cls._providers.keys())

    @classmethod
    def get_aliases(cls) -> Mapping[str, str]:
        """Return a read-only view of known aliases."""
        return dict(cls._aliases)

    @classmethod
    def register_provider(
        cls,
        name: str,
        provider_class: Type[BaseEmbedding],
        *,
        aliases: Optional[List[str]] = None,
        overwrite: bool = False,
    ) -> None:
        """
        Register a new embedding provider.

        Args:
            name: canonical provider name to register
            provider_class: class inheriting from BaseEmbedding
            aliases: optional list of alias strings mapping to `name`
            overwrite: allow replacing an existing provider of the same name

        Raises:
            ValueError: if provider_class is invalid or name exists and overwrite=False
        """
        if not issubclass(provider_class, BaseEmbedding):
            raise ValueError("Provider class must inherit from BaseEmbedding")

        key = cls._normalize_name(name)
        if not overwrite and key in cls._providers:
            raise ValueError(f"Provider {key!r} already exists (use overwrite=True to replace).")

        cls._providers[key] = provider_class
        logger.info("Registered provider %s -> %s", key, provider_class.__name__)

        for al in aliases or []:
            alias_key = cls._normalize_name(al)
            cls._aliases[alias_key] = key
            logger.info("Registered alias %s -> %s", alias_key, key)


    @classmethod
    def _normalize_name(cls, name: str) -> str:
        """Trim/Lowercase and resolve aliases to canonical provider name."""
        key = (name or "").strip().lower()
        return cls._aliases.get(key, key)

    @classmethod
    def _normalize_kwargs(cls, canonical_name: str, kwargs: Dict) -> Dict:
        """
        Normalize kwargs for a given canonical provider.

        - sentence_transformer:
            * accept 'name' or 'model_name' and wrap into EmbeddingConfig if 'config' missing.
        - others: passthrough.
        """
        if canonical_name == "sentence_transformer":
            if "config" not in kwargs:
                # Accept common synonyms
                model_name = kwargs.pop("name", None) or kwargs.pop("model_name", None)
                if model_name:
                    kwargs["config"] = EmbeddingConfig(name=model_name)
        return kwargs
