"""
Similarity-based search for RAG system
"""
from typing import List, Dict, Any, Optional, Literal, Tuple
from data.indexing.vector_store import PgVectorStore
from data.embeddings.embeddings import Embeddings
from common.config import EmbeddingConfigs
from common.logger import logger

Metric = Literal["cosine", "ip", "l2"]
OPS = {"cosine": "<=>", "ip": "<#>", "l2": "<->"}
OPCLASS = {"cosine": "vector_cosine_ops", "ip": "vector_ip_ops", "l2": "vector_l2_ops"}

class SimilaritySearcher:
    """
    HNSW similarity search (pgvector).
    Provides vector similarity search capabilities for the RAG system.
    Trả về CHUẨN: List[{"id": ..., "distance": float, "metadata": {...}}]
    """
    def __init__(self,
                 vector_store: Optional[PgVectorStore] = None,
                 embedding_model: Optional[Any] = None,
                 default_metric: Metric = "cosine",
                 ef_search: int = 64,
                 config: Optional[EmbeddingConfigs] = None):
        self.vector_store = vector_store or PgVectorStore()

        # Use provided embedding model or create from config
        if embedding_model:
            self.embedding_model = embedding_model
        elif config:
            provider = config.provider
            self.embedding_model = Embeddings.create_embedding(provider)
        else:
            self.embedding_model = Embeddings.create_embedding('sentence_transformer')

        self.metric: Metric = default_metric
        self.ef_search = ef_search

    def _ensure_index(self, table: str, col: str, metric: Metric):
        sql = f"""
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE tablename = '{table}' AND indexname = 'idx_{table}_{col}_hnsw'
          ) THEN
            EXECUTE 'CREATE INDEX idx_{table}_{col}_hnsw
                     ON {table} USING hnsw ({col} {OPCLASS[metric]})
                     WITH (m = 16, ef_construction = 200)';
          END IF;
        END$$;
        """
        self.vector_store.exec_sql(sql)

    def search(self,
               table: str,
               k: int = 10,
               query: Optional[str] = None,
               query_vector: Optional[List[float]] = None,
               column: str = "embedding",
               metric: Optional[Metric] = None,
               where: Optional[str] = None,
               id_col: str = "id",
               meta_cols: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Top-k HNSW search (no threshold).
        Output chuẩn: [{"id": <id>, "distance": <float>, "metadata": {...}}]
        """
        met = metric or self.metric
        op = OPS[met]
        if query_vector is None:
            if not query:
                raise ValueError("Provide either query text or query_vector")
            query_vector = self.embedding_model.embed_query(query)

        self.vector_store.exec_sql(f"SET hnsw.ef_search = {int(self.ef_search)};")
        self._ensure_index(table, column, met)

        meta_cols = meta_cols or ["content"]  # tuỳ schema của bạn
        select_cols = ", ".join([id_col] + meta_cols)
        dist_expr = f"{column} {op} %s"
        where_sql = f"WHERE ({where})" if where else ""

        sql = f"""
        SELECT {select_cols}, {dist_expr} AS distance
        FROM {table}
        {where_sql}
        ORDER BY {dist_expr} ASC
        LIMIT %s;
        """

        params = [query_vector, int(k)]

        rows = self.vector_store.query(sql, params=params)

        results: List[Dict[str, Any]] = []
        for r in rows:
            meta = {c: r[c] for c in meta_cols if c in r}
            results.append({
                "id": r[id_col],
                "distance": float(r["distance"]),
                "metadata": meta
            })
        return results

    def search_by_text(self, table: str, query_text: str, k: int = 10, **kwargs) -> List[Tuple[float, Dict[str, Any]]]:
        """
        Search using text query, returning (score, metadata) tuples as expected by other components.
        This method converts the distance-based results to similarity scores (higher is better).
        """
        results = self.search(table=table, query=query_text, k=k, **kwargs)
        # Convert distances to similarity scores (higher = more similar)
        converted_results = []
        for result in results:
            # Convert distance to similarity score: closer to 0 distance = higher similarity
            similarity_score = 1.0 / (1.0 + result["distance"])  # Convert distance to similarity
            converted_results.append((
                similarity_score,
                result["metadata"]
            ))
        return converted_results

    def search_by_vector(self, table: str, query_vector: List[float], k: int = 10, **kwargs) -> List[Tuple[float, Dict[str, Any]]]:
        """
        Search using pre-computed query vector, returning (score, metadata) tuples as expected by other components.
        This method converts the distance-based results to similarity scores (higher is better).
        """
        results = self.search(table=table, query_vector=query_vector, k=k, **kwargs)
        # Convert distances to similarity scores (higher = more similar)
        converted_results = []
        for result in results:
            # Convert distance to similarity score: closer to 0 distance = higher similarity
            similarity_score = 1.0 / (1.0 + result["distance"])  # Convert distance to similarity
            converted_results.append((
                similarity_score,
                result["metadata"]
            ))
        return converted_results

