"""
Batch embedding processing
"""

import os, time, json, random
from typing import Iterable, Dict, Any, List, Tuple
from data.embeddings.embeddings import Embeddings

def yield_batches(items: List[Any], batch_size: int):
    for i in range(0, len(items), batch_size):
        yield items[i:i+batch_size]

def backoff_sleep(attempt, base=1.5, cap=30.0):
    t = min(cap, (base ** attempt)) * (1 + 0.25*random.random())
    time.sleep(t)

def batch_embed_texts(
    texts: List[str],
    *,
    provider: str = "openai",
    batch_size: int = 64,
    max_retries: int = 5,
    out_jsonl: str | None = None,
    **provider_kwargs,
) -> Tuple[List[List[float]], int]:
    all_vecs: List[List[float]] = []
    dim: int = 0
    if out_jsonl:
        f = open(out_jsonl, "w", encoding="utf-8")
    else:
        f = None

    try:
        for batch in yield_batches(texts, batch_size):
            # retry loop
            attempt = 0
            while True:
                try:
                    vecs, dim = Embeddings.encode_texts(
                        batch, provider=provider, batch_size=len(batch), **provider_kwargs
                    )
                    break
                except Exception as e:
                    attempt += 1
                    if attempt > max_retries:
                        raise
                    backoff_sleep(attempt)
            # collect
            all_vecs.extend(vecs)
            # checkpoint
            if f:
                for v in vecs:
                    rec = {"vector": v if isinstance(v, list) else list(v)}
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    finally:
        if f:
            f.close()
    return all_vecs, dim
