"""
Similarity-based search for RAG system
"""
from typing import List, Dict, Any, Optional, Literal, Tuple
from data.indexing.vector_store import PgVectorStore
from data.embeddings.embeddings import Embeddings
from common.config import EmbeddingConfigs
from common.utils.security import validate_identifier

Metric = Literal["cosine", "ip", "l2"]
OPS = {"cosine": "<=>", "ip": "<#>", "l2": "<->"}
OPCLASS = {"cosine": "vector_cosine_ops", "ip": "vector_ip_ops", "l2": "vector_l2_ops"}

class SimilaritySearcher:
    """
    HNSW similarity search (pgvector).
    Provides vector similarity search capabilities for the RAG system.
    Returns: List[{"id": ..., "distance": float, "metadata": {...}}]
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
        self.OPS = OPS

    def _ensure_index(self, table: str, col: str, metric: Metric):
        # Validate identifiers to prevent SQL injection
        validated_table = validate_identifier(table, "table name")
        validated_col = validate_identifier(col, "column name")
        
        sql = f"""
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE tablename = '{validated_table}' AND indexname = 'idx_{validated_table}_{validated_col}_hnsw'
          ) THEN
            EXECUTE 'CREATE INDEX idx_{validated_table}_{validated_col}_hnsw
                     ON {validated_table} USING hnsw ({validated_col} {OPCLASS[metric]})
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
        Returns: [{"id": <id>, "distance": <float>, "metadata": {...}}]
        """
        # Validate identifiers to prevent SQL injection
        validated_table = validate_identifier(table, "table name")
        validated_column = validate_identifier(column, "column name")
        validated_id_col = validate_identifier(id_col, "column name")
        validated_meta_cols = []
        if meta_cols:
            for col in meta_cols:
                validated_meta_cols.append(validate_identifier(col, "column name"))
        else:
            validated_meta_cols = ["content"]  # depends on your schema

        met = metric or self.metric
        op = OPS[met]
        if query_vector is None:
            if not query:
                raise ValueError("Provide either query text or query_vector")
            query_vector = self.embedding_model.encode(query)

        # Convert numpy array to list and format as PostgreSQL vector literal
        if hasattr(query_vector, 'tolist'):
            query_vector = query_vector.tolist()
        query_vector_str = '[' + ','.join(str(float(x)) for x in query_vector) + ']'

        self.vector_store.exec_sql(f"SET hnsw.ef_search = {int(self.ef_search)};")
        self._ensure_index(validated_table, validated_column, met)

        select_cols = ", ".join([validated_id_col] + validated_meta_cols)
        dist_expr = f"{validated_column} {op} CAST(:qvec AS vector)"
        where_sql = f"WHERE ({where})" if where else ""

        sql = f"""
        SELECT {select_cols}, {dist_expr} AS distance
        FROM {validated_table}
        {where_sql}
        ORDER BY {dist_expr} ASC
        LIMIT :k;
        """

        params = {"qvec": query_vector_str, "k": int(k)}

        rows = self.vector_store.query(sql, params=params)

        results: List[Dict[str, Any]] = []
        for r in rows:
            meta = {c: r[c] for c in validated_meta_cols if c in r}
            results.append({
                "id": r[validated_id_col],
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


