# data/embeddings/embeddings.py
from __future__ import annotations
import inspect
from typing import List, Dict, Tuple, Callable, Type, Any, Sequence

from .models import (
    BaseEmbedding,
    EmbeddingConfig,
    OpenAIEmbedding,
    GoogleEmbedding,
    MistralEmbedding,
    SentenceTransformerEmbedding,
)


def _infer_dim(emb: Any) -> int:
    """
    Suy ra chiều embedding:
      1) Thử thuộc tính phổ biến: dim / dimension / output_dim / embedding_dim
      2) Thử trong config: config.dim
      3) Cuối cùng: encode([' ']) và lấy len(vector), rồi cache vào emb.dim
    """
    for attr in ("dim", "dimension", "output_dim", "embedding_dim"):
        if hasattr(emb, attr):
            try:
                return int(getattr(emb, attr))
            except Exception:
                pass

    cfg = getattr(emb, "config", None)
    if cfg is not None and hasattr(cfg, "dim"):
        try:
            d = int(getattr(cfg, "dim"))
            try: setattr(emb, "dim", d)   # cache cho lần sau
            except Exception: pass
            return d
        except Exception:
            pass

    # Fall-back: hỏi trực tiếp encoder
    try:
        vec = emb.encode([" "])[0]
        d = len(vec)
        try: setattr(emb, "dim", d)       # cache
        except Exception: pass
        return d
    except Exception as e:
        raise ValueError(
            "Cannot infer embedding dimension; please expose `.dim` "
            "hoặc cung cấp `config.dim` cho provider."
        ) from e

"""
Usage example:

from data.embeddings.embeddings import Embeddings

# 1) Lấy encoder & dim:
encode, dim, inst = Embeddings.get_encoder("sentence_transformer", name="all-MiniLM-L6-v2")
vecs = encode(["text a", "text b"])

# 2) Embed trực tiếp list chunk (mặc định lấy thuộc tính .text và gán vào .vector):
chunks, dim = Embeddings.embed_chunks(chunks, provider="openai", api_key="...", model="text-embedding-3-small")
"""

class Embeddings:
    """Factory & helpers for embedding providers, kèm tiện ích embed theo chunk."""

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

    # Cache instance theo (provider + model/config)
    _CACHE: Dict[str, BaseEmbedding] = {}

    # ---------- Factory ----------
    @classmethod
    def create_embedding(cls, provider: str, **kwargs: Any) -> BaseEmbedding:
        prov = cls._normalize_provider(provider)
        if prov not in cls._providers:
            raise ValueError(
                f"Unsupported embedding provider: {provider}. "
                f"Available: {', '.join(sorted(cls._providers))}"
            )

        # ---------- Chuẩn hoá kwargs theo provider ----------
        # Alias phổ biến: snake_case -> camelCase
        if prov in {"openai", "google", "mistral"}:
            if "api_key" in kwargs and "apiKey" not in kwargs:
                kwargs["apiKey"] = kwargs.pop("api_key")
            if "base_url" in kwargs and "baseUrl" not in kwargs:
                kwargs["baseUrl"] = kwargs.pop("base_url")
            # map model/name -> modelName (nếu class không dùng config)
            if ("model" in kwargs or "name" in kwargs) and "modelName" not in kwargs:
                kwargs["modelName"] = kwargs.pop("model", kwargs.pop("name", None))

        # SentenceTransformer: ưu tiên config EmbeddingConfig(name=...)
        if cls._providers[prov] is SentenceTransformerEmbedding:
            if "config" not in kwargs:
                model_name = kwargs.pop("name", kwargs.pop("model", "all-MiniLM-L6-v2"))
                kwargs["config"] = EmbeddingConfig(name=model_name)

        # ---------- Lọc kwargs theo chữ ký __init__ ----------
        # Một số class không nhận 'model' hay 'modelName' → ta tự rơi về config
        ProviderClass = cls._providers[prov]
        sig = inspect.signature(ProviderClass.__init__)
        allowed = set(sig.parameters.keys()) - {"self", "*", "**"}
        # nếu có EmbeddingConfig thì chuẩn bị fallback
        cfg = None
        if "config" in allowed:
            # nếu user truyền config sẵn thì giữ nguyên
            if "config" in kwargs and not isinstance(kwargs["config"], EmbeddingConfig):
                # user truyền gì đó kỳ → cố tạo EmbeddingConfig từ name/model/modelName
                name_guess = kwargs.pop("config", None)
                kwargs["config"] = EmbeddingConfig(name=str(name_guess))
            elif "config" not in kwargs:
                # nếu class không nhận model/modelName, sẽ tạo config phía dưới
                cfg = None

        # Nếu __init__ KHÔNG có tham số 'modelName' / 'model', bỏ chúng để tránh TypeError
        for k in ["modelName", "model", "name"]:
            if k in kwargs and k not in allowed:
                # giữ tạm để có thể dùng tạo config ở dưới
                if cfg is None and isinstance(kwargs.get(k), str):
                    cfg = kwargs.get(k)
                kwargs.pop(k)

        # Nếu class nhận 'config' mà ta có cfg (tên model) thì tạo EmbeddingConfig
        if "config" in allowed and "config" not in kwargs and cfg:
            kwargs["config"] = EmbeddingConfig(name=str(cfg))

        # Cuối cùng: chỉ giữ các tham số có trong chữ ký để tránh unexpected kwargs
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in allowed}

        # ---------- Cache ----------
        key = cls._cache_key(prov, filtered_kwargs)
        if key in cls._CACHE:
            return cls._CACHE[key]

        # ---------- Khởi tạo ----------
        try:
            inst = ProviderClass(**filtered_kwargs)
        except ImportError as e:
            raise ValueError(f"{prov} provider is missing optional dependencies: {e}") from e
        except TypeError as e:
            # Thử fallback cuối: nếu có thể truyền qua EmbeddingConfig mà chưa truyền
            if "config" in allowed and "config" not in filtered_kwargs:
                model_name = (
                    kwargs.get("modelName")
                    or kwargs.get("model")
                    or kwargs.get("name")
                    or None
                )
                try_kwargs = dict(filtered_kwargs)
                try_kwargs["config"] = EmbeddingConfig(name=str(model_name or "default"))
                try:
                    inst = ProviderClass(**try_kwargs)
                except Exception as e2:
                    raise ValueError(f"Failed to create {prov} embedding: {e2}") from e2
            else:
                raise ValueError(f"Failed to create {prov} embedding: {e}") from e
        except Exception as e:
            raise ValueError(f"Failed to create {prov} embedding: {e}") from e

        cls._CACHE[key] = inst
        return inst


    @classmethod
    def get_encoder(
        cls, provider: str, **kwargs: Any
    ) -> Tuple[Callable[[List[str]], List[List[float]]], int, Any]:
        emb = cls.create_embedding(provider, **kwargs)
        dim = _infer_dim(emb)   # ✅ thay vì emb.dim
        return emb.encode, dim, emb

    

    @classmethod
    def encode_texts(
        cls,
        texts: Sequence[str],
        provider: str = "sentence_transformer",
        batch_size: int = 64,
        **provider_kwargs: Any,
    ) -> Tuple[List[List[float]], int]:
        """
        Encode một list chuỗi. Trả về (vectors, dim).
        """
        encode, dim, _ = cls.get_encoder(provider, **provider_kwargs)
        vectors: List[List[float]] = []
        if not texts:
            return vectors, dim

        for i in range(0, len(texts), batch_size):
            batch = list(texts[i : i + batch_size])
            vecs = encode(batch)
            vectors.extend(vecs)
        return vectors, dim

    @classmethod
    def embed_chunks(
        cls,
        chunks: Sequence[Any],
        provider: str = "sentence_transformer",
        *,
        text_attr: str = "text",
        vector_attr: str = "vector",
        batch_size: int = 64,
        **provider_kwargs: Any,
    ) -> Tuple[List[Any], int]:
        """
        Embed trực tiếp danh sách chunk (ví dụ ChunkRecord):
          - Lấy nội dung từ `getattr(chunk, text_attr)` (mặc định 'text')
          - Gán vector vào `setattr(chunk, vector_attr, vector)` (mặc định 'vector')

        Trả về: (chunks (đã gán vector), embedding_dim)

        Example:
            chunks, dim = Embeddings.embed_chunks(
                chunks,
                provider="openai",
                api_key="...",
                model="text-embedding-3-small",
                batch_size=128,
            )
        """
        if not chunks:
            return list(chunks), 0

        # Lấy list văn bản từ chunks
        texts: List[str] = []
        for c in chunks:
            try:
                t = getattr(c, text_attr)
            except AttributeError as e:
                raise AttributeError(
                    f"Chunk object {type(c)} has no attribute '{text_attr}'. "
                    "Use text_attr=... để đổi tên field."
                ) from e
            if not isinstance(t, str):
                raise TypeError(f"Chunk.{text_attr} must be str, got {type(t)}")
            texts.append(t)

        vectors, dim = cls.encode_texts(
            texts, provider=provider, batch_size=batch_size, **provider_kwargs
        )

        # Gán vector vào từng chunk
        for c, v in zip(chunks, vectors):
            setattr(c, vector_attr, v)

        return list(chunks), dim

    @classmethod
    def from_settings(cls, settings) -> BaseEmbedding:
        prov = getattr(settings, "EMBEDDING_BACKEND", "sentence_transformer")
        model = getattr(settings, "EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        api_key = getattr(settings, "EMBEDDING_API_KEY", None)
        base_url = getattr(settings, "EMBEDDING_BASE_URL", None)

        kwargs: Dict[str, Any] = {"name": model}
        # dùng alias snake_case; create_embedding sẽ map sang camelCase khi cần
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
