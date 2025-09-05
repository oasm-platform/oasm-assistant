# -*- coding: utf-8 -*-
"""
overview:
- Purpose: Efficiently embed large collections of texts in batches with robust retry,
  exponential backoff (with jitter), and optional JSONL checkpointing.
- Flow:
    1) Batch: split input texts into fixed-size batches
    2) Encode: call a provider (via your Embeddings registry) once per batch
    3) Retry: transient failures are retried with exponential backoff + jitter
    4) Checkpoint: optionally write vectors (and/or source text) to a JSONL file
    5) Output: return the full list of vectors and the inferred embedding dimension
- Integration: Uses your project's `Embeddings` factory/registry to create providers
  (or falls back to `Embeddings.encode_texts(...)` if that utility exists).

Design notes:
- `BatchEmbedConfig`: stores configuration and validates inputs
- `JsonlWriter`: safe context-managed writer for incremental checkpointing
- `BatchEmbedder`: main orchestrator with internal helpers for batching, backoff, and encoding
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from common.logger import logger
from data.embeddings.embeddings import Embeddings 


# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------
@dataclass(frozen=True)
class BatchEmbedConfig:
    """
    Cấu hình cho pipeline nhúng theo batch.

    Attributes:
        provider: Tên provider trong registry (vd: "openai", "google", "mistral",
                  "sentence_transformer", ...; alias được registry chuẩn hoá).
        batch_size: Số phần tử mỗi batch.
        max_retries: Số lần retry tối đa khi provider lỗi tạm thời.
        backoff_base: Cơ số lũy thừa của backoff (>= 1.0).
        backoff_cap: Giới hạn trên cho thời gian ngủ giữa các lần retry (giây).
        out_jsonl: Đường dẫn file JSONL để checkpoint (None → không ghi).
        include_text_in_jsonl: Nếu True, ghi cả text gốc vào JSONL (phục vụ debug).
        jsonl_mode: Chế độ mở file, mặc định 'w' (ghi mới). Có thể dùng 'a' để nối.
        provider_kwargs: Tham số truyền vào khi tạo provider (api_key, model, endpoint, ...).
        reuse_provider: Nếu True, tạo 1 instance provider và tái sử dụng cho mọi batch
                        (giảm overhead so với tạo lại mỗi lần).
    """
    provider: str = "openai"
    batch_size: int = 64
    max_retries: int = 5
    backoff_base: float = 1.5
    backoff_cap: float = 30.0
    out_jsonl: Optional[str] = None
    include_text_in_jsonl: bool = False
    jsonl_mode: str = "w"
    provider_kwargs: Dict[str, Any] = field(default_factory=dict)
    reuse_provider: bool = True

    def validate(self) -> None:
        if self.batch_size <= 0:
            raise ValueError("batch_size must be > 0")
        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if self.backoff_base < 1.0:
            raise ValueError("backoff_base must be >= 1.0")
        if self.backoff_cap <= 0:
            raise ValueError("backoff_cap must be > 0")
        if self.jsonl_mode not in ("w", "a"):
            raise ValueError("jsonl_mode must be 'w' or 'a'")


# ------------------------------------------------------------------------------
# Utilities
# ------------------------------------------------------------------------------
def _yield_batches(items: Sequence[Any], batch_size: int) -> Iterable[Sequence[Any]]:
    """Chia items thành các lô (batches) kích thước batch_size."""
    for i in range(0, len(items), batch_size):
        yield items[i : i + batch_size]


def _backoff_sleep(attempt: int, base: float, cap: float) -> None:
    """Ngủ theo backoff lũy thừa + jitter để hạn chế đụng trần rate-limit."""
    t = min(cap, (base ** attempt)) * (1.0 + 0.25 * random.random())
    time.sleep(t)


class JsonlWriter:
    """
    Writer JSONL dùng context-manager, đảm bảo đóng file an toàn.
    Mỗi `write_record` sẽ ghi một dòng JSON độc lập (phù hợp checkpoint).
    """

    def __init__(self, path: Optional[str], mode: str = "w") -> None:
        self._path = path
        self._mode = mode
        self._fh = None  # type: Optional[Any]

    def __enter__(self) -> "JsonlWriter":
        if self._path:
            self._fh = open(self._path, self._mode, encoding="utf-8")
            logger.info("Opened checkpoint JSONL: %s (mode=%s)", self._path, self._mode)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._fh:
            self._fh.close()
            logger.info("Closed checkpoint JSONL: %s", self._path)

    def write_record(self, rec: Dict[str, Any]) -> None:
        if self._fh:
            self._fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ------------------------------------------------------------------------------
# Main Orchestrator
# ------------------------------------------------------------------------------
class BatchEmbedder:
    """
    Pipeline nhúng văn bản theo lô (batch) với retry/backoff & checkpoint JSONL.

    Tự động phát hiện hàm encode phù hợp theo thứ tự ưu tiên:
      1) Provider instance method: `encode_texts(batch)` hoặc `encode(batch)`
      2) Fallback: `Embeddings.encode_texts(batch, provider=..., **kwargs)`

    Example:
        cfg = BatchEmbedConfig(
            provider="openai",
            batch_size=128,
            out_jsonl="vectors.jsonl",
            provider_kwargs={"model": "text-embedding-3-small"},
        )
        embedder = BatchEmbedder(cfg)
        vectors, dim = embedder.run(texts)
    """

    def __init__(self, config: BatchEmbedConfig) -> None:
        self.config = config
        self.config.validate()

        self._provider_instance = None
        if self.config.reuse_provider:
            self._provider_instance = self._create_provider_instance()

    # ---------------------- Public API ----------------------

    def run(self, texts: Sequence[str]) -> Tuple[List[List[float]], int]:
        """
        Thực thi pipeline nhúng trên toàn bộ `texts`.

        Returns:
            (all_vectors, inferred_dim)
        """
        if not texts:
            logger.info("No texts provided. Returning empty result.")
            return [], 0

        all_vecs: List[List[float]] = []
        inferred_dim: int = 0

        with JsonlWriter(self.config.out_jsonl, mode=self.config.jsonl_mode) as writer:
            for idx, batch in enumerate(_yield_batches(texts, self.config.batch_size), start=1):
                logger.info("Processing batch %d (size=%d)", idx, len(batch))
                vecs, inferred_dim = self._encode_with_retry(batch)

                # Thu thập
                all_vecs.extend(vecs)

                # Checkpoint JSONL (nếu cấu hình)
                self._checkpoint(writer, batch, vecs)

        logger.info("Completed. Total vectors: %d | dim: %s", len(all_vecs), inferred_dim)
        return all_vecs, inferred_dim

    # ---------------------- Internals ----------------------

    def _create_provider_instance(self):
        """
        Tạo instance provider qua registry (`Embeddings.create_embedding`).
        Trả về None nếu tạo thất bại (để fallback sang Embeddings.encode_texts).
        """
        try:
            inst = Embeddings.create_embedding(self.config.provider, **self.config.provider_kwargs)
            logger.debug("Created provider instance: %s", self.config.provider)
            return inst
        except Exception as e:
            logger.warning(
                "Could not create provider instance (%s). Will fallback to Embeddings.encode_texts if available. Error: %r",
                self.config.provider, e
            )
            return None

    def _call_encoder(self, batch: Sequence[str]) -> Tuple[List[List[float]], int]:
        """
        Gọi encoder tương thích:
          - Nếu có provider instance: ưu tiên gọi phương thức `encode_texts` hoặc `encode`.
          - Nếu không: thử gọi `Embeddings.encode_texts(...)`.
          - Chuẩn hoá đầu ra: List[List[float]], dim (suy ra nếu provider không trả dim).
        """
        # 1) Provider instance path
        if self._provider_instance is None and not self.config.reuse_provider:
            # nếu không reuse, mỗi batch tạo instance mới (ít khuyến nghị, nhưng hỗ trợ)
            self._provider_instance = self._create_provider_instance()

        if self._provider_instance is not None:
            inst = self._provider_instance
            if hasattr(inst, "encode_texts"):
                result = inst.encode_texts(list(batch))  # type: ignore[attr-defined]
            elif hasattr(inst, "encode"):
                result = inst.encode(list(batch))  # type: ignore[attr-defined]
            else:
                raise AttributeError(
                    f"Provider instance {type(inst).__name__} has no 'encode_texts' or 'encode' method."
                )
            vecs, dim = self._normalize_result(result)

            # nếu không reuse, giải phóng instance sau khi xong
            if not self.config.reuse_provider:
                self._provider_instance = None

            return vecs, dim

        # 2) Fallback: Embeddings.encode_texts (nếu có trong codebase của bạn)
        if hasattr(Embeddings, "encode_texts"):
            result = Embeddings.encode_texts(
                list(batch),
                provider=self.config.provider,
                batch_size=len(batch),
                **self.config.provider_kwargs,
            )
            vecs, dim = self._normalize_result(result)
            return vecs, dim

        # 3) If neither path exists, fail loudly
        raise RuntimeError(
            "No valid encoding path found. Please ensure either:\n"
            " - Embeddings.create_embedding(...) returns an object with 'encode_texts' or 'encode', OR\n"
            " - Embeddings.encode_texts(...) utility is implemented."
        )

    def _encode_with_retry(self, batch: Sequence[str]) -> Tuple[List[List[float]], int]:
        """Gọi encoder với retry/backoff khi gặp lỗi tạm thời."""
        attempt = 0
        while True:
            try:
                vecs, dim = self._call_encoder(batch)
                return vecs, dim
            except Exception as e:
                attempt += 1
                if attempt > self.config.max_retries:
                    logger.error(
                        "Max retries exceeded for a batch of size %d. Last error: %r",
                        len(batch), e
                    )
                    raise
                logger.warning(
                    "Provider call failed (attempt %d/%d). Retrying... Error: %r",
                    attempt, self.config.max_retries, e
                )
                _backoff_sleep(
                    attempt=attempt,
                    base=self.config.backoff_base,
                    cap=self.config.backoff_cap,
                )

    @staticmethod
    def _normalize_result(result: Any) -> Tuple[List[List[float]], int]:
        """
        Chuẩn hoá output của provider thành (vectors, dim).
        - Accepts:
            * List[List[float]] → suy ra dim từ phần tử đầu
            * Tuple[List[List[float]], int] → dùng trực tiếp
        """
        if isinstance(result, tuple) and len(result) == 2:
            vecs, dim = result
        else:
            vecs = result  # type: ignore[assignment]
            dim = 0

        # Convert tất cả về List[List[float]]
        vecs = [v if isinstance(v, list) else list(v) for v in vecs]

        # Suy ra dim nếu chưa có
        if not dim:
            dim = len(vecs[0]) if vecs else 0

        return vecs, int(dim)

    def _checkpoint(self, writer: JsonlWriter, batch: Sequence[str], vecs: Sequence[Sequence[float]]) -> None:
        """Ghi checkpoint các vector (và tuỳ chọn text) vào JSONL nếu được cấu hình."""
        if not self.config.out_jsonl:
            return

        if self.config.include_text_in_jsonl:
            for text, v in zip(batch, vecs):
                writer.write_record({"text": text, "vector": [float(x) for x in v]})
        else:
            for v in vecs:
                writer.write_record({"vector": [float(x) for x in v]})



# ------------------------------------------------------------------------------
# Quick usage demo (remove if integrating into your package)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    # Ví dụ chạy nhanh
    sample_texts = [f"Document {i}" for i in range(250)]

    cfg = BatchEmbedConfig(
        provider="openai",
        batch_size=64,
        max_retries=5,
        backoff_base=1.5,
        backoff_cap=30.0,
        out_jsonl="embeddings_checkpoint.jsonl",
        include_text_in_jsonl=False,   # đổi True nếu muốn lưu cả text
        jsonl_mode="w",
        provider_kwargs={
            # ví dụ: "model": "text-embedding-3-small",
            # "api_key": "...",
        },
        reuse_provider=True,
    )

    embedder = BatchEmbedder(cfg)
    vectors, dim = embedder.run(sample_texts)
    logger.info("Total vectors: %d | dim: %d", len(vectors), dim)
