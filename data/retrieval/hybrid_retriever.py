from typing import List, Dict, Any, Optional, Protocol
import re
from .similarity_searcher import SimilaritySearcher
from data.indexing.vector_store import PgVectorStore
from data.embeddings.embeddings import Embeddings
from common.config import EmbeddingConfigs
from common.logger import logger

# Compile regex once for efficiency
_ident_re = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

def _assert_ident(s: str, name: str):
    """Validate SQL identifier to prevent injection."""
    if not _ident_re.match(s or ""):
        raise ValueError(f"Invalid SQL identifier for {name}: {s}")

class Ranker(Protocol):
    def rank(self, items: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        ...

class SimpleRanker:
    def __init__(self, threshold: float = 0.0):
        self.threshold = threshold

    def rank(self, items: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        filtered_items = [item for item in items if item.get('score', 0) >= self.threshold]
        return sorted(filtered_items, key=lambda x: x.get('score', 0), reverse=True)

class HybridRetriever:
    def __init__(
        self,
        vector_store: Optional[PgVectorStore] = None,
        config: Optional[EmbeddingConfigs] = None,
        similarity_searcher: Optional[SimilaritySearcher] = None,
        keyword_weight: float = 0.4,
        vector_weight: float = 0.6,
        ef_search: int = 64,
        ft_lang: str = "simple",  
        ranker: Optional[Ranker] = None,
    ):
        self.vector_store = vector_store or PgVectorStore()
        self.config = config
        self.similarity_searcher = similarity_searcher or SimilaritySearcher(
            vector_store=self.vector_store,
            config=config,
            default_metric="cosine",
            ef_search=ef_search,
        )
        self.keyword_weight = float(keyword_weight)
        self.vector_weight  = float(vector_weight)
        if abs(self.keyword_weight + self.vector_weight - 1.0) > 1e-6:
            logger.warning("keyword_weight + vector_weight != 1.0; sẽ dùng như đã cho.")
        self.ft_lang = ft_lang
        self.ranker = ranker or SimpleRanker(threshold=0.0)

    # ---------- FAST PATH: 1 round-trip SQL ----------
    def hybrid_search(
        self,
        table: str,
        qtext: str,
        k: int = 10,
        id_col: str = "id",
        title_col: str = "title",
        content_col: str = "content",
        embedding_col: str = "embedding",
        tsv_col: str = "tsv",
        where: Optional[str] = None,
        candidates_each: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        One-shot hybrid search (vector + FTS). Returns sorted top-k using ranker.
        Output: [{id, score, vec_score, text_score, metadata:{...}}]
        """
        # Validate identifiers to avoid SQL injection on names
        for name, val in [
            ("table", table), ("id_col", id_col), ("title_col", title_col),
            ("content_col", content_col), ("embedding_col", embedding_col),
            ("tsv_col", tsv_col),
        ]: _assert_ident(val, name)

        # Prepare inputs
        qvec = self.similarity_searcher.embedding_model.embed_query(qtext)
        op   = self.similarity_searcher.OPS[self.similarity_searcher.metric]  # '<=>', '<#>', '<->'
        self.vector_store.exec_sql(f"SET hnsw.ef_search = {int(self.similarity_searcher.ef_search)};")

        # where clause pieces
        where_vec = f"WHERE ({where})" if where else ""
        where_txt = f"AND ({where})"   if where else ""

        # NOTE:
        #  - vector vscore = 1 - distance (cosine) -> [0..1] (xấp xỉ)
        #  - FTS dùng ts_rank(tsv, plainto_tsquery(ft_lang, $2))
        #  - Chuẩn hoá min-max trong batch union để cân bằng thang điểm
        sql = f"""
        WITH vec AS (
          SELECT {id_col} AS id,
                 (1 - ({embedding_col} {op} %s)) AS vscore
          FROM {table}
          {where_vec}
          ORDER BY {embedding_col} {op} %s
          LIMIT %s
        ),
        txt AS (
          SELECT {id_col} AS id,
                 ts_rank({tsv_col}, plainto_tsquery(%s, %s)) AS tscore
          FROM {table}
          WHERE {tsv_col} @@ plainto_tsquery(%s, %s)
          {where_txt}
          ORDER BY tscore DESC
          LIMIT %s
        ),
        u AS (
          SELECT id,
                 COALESCE(MAX(vscore), 0) AS vscore,
                 COALESCE(MAX(tscore), 0) AS tscore
          FROM (
            SELECT * FROM vec
            UNION ALL
            SELECT * FROM txt
          ) s
          GROUP BY id
        ),
        stats AS (
          SELECT
            MIN(vscore) AS vmin, MAX(vscore) AS vmax,
            MIN(tscore) AS tmin, MAX(tscore) AS tmax
          FROM u
        ),
        norm AS (
          SELECT u.id,
                 CASE WHEN (stats.vmax - stats.vmin) > 1e-9
                      THEN (u.vscore - stats.vmin)/(stats.vmax - stats.vmin)
                      ELSE u.vscore END AS vnorm,
                 CASE WHEN (stats.tmax - stats.tmin) > 1e-9
                      THEN (u.tscore - stats.tmin)/(stats.tmax - stats.tmin)
                      ELSE u.tscore END AS tnorm
          FROM u, stats
        )
        SELECT d.{id_col} AS id,
               d.{title_col} AS title,
               d.{content_col} AS content,
               norm.vnorm AS vec_score,
               norm.tnorm AS text_score,
               (%s * norm.vnorm + %s * norm.tnorm) AS hybrid_score
        FROM norm
        JOIN {table} d ON d.{id_col} = norm.id
        ORDER BY hybrid_score DESC
        LIMIT %s;
        """

        params = [
            qvec, qvec, int(candidates_each),     # vec
            self.ft_lang, qtext, self.ft_lang, qtext, int(candidates_each),  # txt
            float(self.vector_weight), float(self.keyword_weight), int(k)     # fusion + limit
        ]
        rows = self.vector_store.query(sql, params=params)

        # Pre-allocate list for efficiency
        raw_results = []
        for r in rows:
            raw_results.append({
                "id": r["id"],
                "score": float(r["hybrid_score"]),     # cao hơn = tốt hơn
                "vec_score": float(r["vec_score"]),
                "text_score": float(r["text_score"]),
                "metadata": {
                    "title": r.get("title"),
                    "content": r.get("content"),
                },
            })
        
        # Sử dụng ranker để xếp hạng kết quả
        ranked_results = self.ranker.rank(raw_results, qtext)
        return ranked_results[:k]

    def set_ranker(self, ranker: Ranker):
        """Thiết lập ranker mới để kiểm soát mức độ tương thích"""
        self.ranker = ranker

    def get_ranker(self) -> Ranker:
        """Lấy ranker hiện tại"""
        return self.ranker

    # ---------- FALLBACK----------
    def fallback_hybrid(
        self,
        table: str, qtext: str, k: int = 10,
        id_col: str = "id", content_col: str = "content",
        embedding_col: str = "embedding", tsv_col: str = "tsv",
        where: Optional[str] = None, candidates_each: int = 50
    ) -> List[Dict[str, Any]]:

        try:
            # Vector top-N
            vec_rows = self.similarity_searcher.search(
                table=table, k=candidates_each, query=qtext,
                column=embedding_col, where=where, id_col=id_col,
                meta_cols=[content_col]
            )
            # FTS top-M
            ft_sql = f"""
            SELECT {id_col} AS id,
                   ts_rank({tsv_col}, plainto_tsquery(%s, %s)) AS tscore
            FROM {table}
            WHERE {tsv_col} @@ plainto_tsquery(%s, %s)
            {"AND (" + where + ")" if where else ""}
            ORDER BY tscore DESC
            LIMIT %s;
            """
            ft_rows = self.vector_store.query(ft_sql, params=[self.ft_lang, qtext, self.ft_lang, qtext, int(candidates_each)])

            vmap = {r["id"]: float(1.0 / (1.0 + r["distance"])) for r in vec_rows}  
            tmap = {r["id"]: float(r["tscore"]) for r in ft_rows if "tscore" in r}

            def _minmax(d: Dict[Any, float]) -> Dict[Any, float]:
                if not d: return {}
                vals = list(d.values())
                if not vals: return {}
                mn, mx = min(vals), max(vals)
                if mx - mn < 1e-9: return {k: float(v) for k, v in d.items()}
                return {k: float((v - mn)/(mx - mn)) for k, v in d.items()}

            vnorm, tnorm = _minmax(vmap), _minmax(tmap)
            all_ids = set(vnorm) | set(tnorm)

            # Fetch metadata once
            id_list = list(all_ids)[: max(k, 50)]
            if id_list:  # Only query if there are IDs to fetch
                meta_rows = self.vector_store.query(
                    f"SELECT {id_col} AS id, {content_col} AS content FROM {table} WHERE {id_col} = ANY(%s);",
                    params=[id_list]
                )
                meta = {r["id"]: r.get("content") for r in meta_rows}
            else:
                meta = {}

            # Pre-allocate for efficiency
            scored = []
            for i in all_ids:
                vs, ts = vnorm.get(i, 0.0), tnorm.get(i, 0.0)
                hybrid = self.vector_weight*vs + self.keyword_weight*ts
                scored.append((hybrid, i, vs, ts))

            raw_results = []
            for s, item_id, vs, ts in scored:
                raw_results.append({
                    "id": item_id,
                    "score": float(s),
                    "vec_score": float(vs),
                    "text_score": float(ts),
                    "metadata": {"content": meta.get(item_id)}
                })
            
            ranked_results = self.ranker.rank(raw_results, qtext)
            return ranked_results[:k]
        except Exception as e:
            logger.error(f"fallback_hybrid failed: {e}")
            return []
