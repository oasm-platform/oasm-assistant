"""
Simplified filtering engine for RAG system with database-level optimization
"""
from typing import List, Tuple, Dict, Any, Optional
from data.indexing.vector_store import PgVectorStore
from data.embeddings.embeddings import Embeddings
from common.logger import logger
from data.database import postgres_db as db
from sqlalchemy import text
import math
from datetime import datetime


class FilterEngine:
    """
    Simplified filtering engine for RAG system with database-level optimization.
    """
    
    def __init__(
        self,
        vector_store: Optional[PgVectorStore] = None,
        embedding_model: Optional[Any] = None
    ):
        """
        Initialize the filter engine.
        
        Args:
            vector_store: PgVectorStore instance for database operations
            embedding_model: Embedding model for potential semantic filtering
        """
        self.vector_store = vector_store or PgVectorStore()
        self.embedding_model = embedding_model or Embeddings.create_embedding('sentence_transformer')

    def _build_where_clause(self, filters: Dict[str, Any], table_alias: str = "kb") -> Tuple[str, Dict[str, Any]]:
        """
        Build a WHERE clause from filter dictionary with parameterized values.
        """
        conditions = []
        params = {}
        
        for field, value in filters.items():
            # Handle different types of filter conditions
            if isinstance(value, dict):
                # Handle range queries like {"min": 10, "max": 20}
                if "min" in value and "max" in value:
                    param_min = f"{field}_min"
                    param_max = f"{field}_max"
                    conditions.append(f"{table_alias}.{field} BETWEEN :{param_min} AND :{param_max}")
                    params[param_min] = value["min"]
                    params[param_max] = value["max"]
                elif "gt" in value:
                    param = f"{field}_gt"
                    conditions.append(f"{table_alias}.{field} > :{param}")
                    params[param] = value["gt"]
                elif "gte" in value:
                    param = f"{field}_gte"
                    conditions.append(f"{table_alias}.{field} >= :{param}")
                    params[param] = value["gte"]
                elif "lt" in value:
                    param = f"{field}_lt"
                    conditions.append(f"{table_alias}.{field} < :{param}")
                    params[param] = value["lt"]
                elif "lte" in value:
                    param = f"{field}_lte"
                    conditions.append(f"{table_alias}.{field} <= :{param}")
                    params[param] = value["lte"]
            elif isinstance(value, list):
                # Handle "in" queries
                if len(value) > 0:
                    placeholders = []
                    for i, val in enumerate(value):
                        param = f"{field}_{i}"
                        params[param] = val
                        placeholders.append(f":{param}")
                    conditions.append(f"{table_alias}.{field} IN ({', '.join(placeholders)})")
            else:
                # Handle exact match
                param = f"{field}_eq"
                conditions.append(f"{table_alias}.{field} = :{param}")
                params[param] = value
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        return where_clause, params

    def _build_content_where_clause(
        self,
        include_keywords: Optional[List[str]] = None,
        exclude_keywords: Optional[List[str]] = None,
        text_field: str = "text",
        case_sensitive: bool = False,
        table_alias: str = "kb"
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build a WHERE clause for content keyword filtering.
        """
        conditions = []
        params = {}
        
        # Process include keywords
        if include_keywords:
            for i, keyword in enumerate(include_keywords):
                param = f"include_kw_{i}"
                if case_sensitive:
                    conditions.append(f"{table_alias}.{text_field} LIKE :{param}")
                else:
                    conditions.append(f"LOWER({table_alias}.{text_field}) LIKE LOWER(:{param})")
                params[param] = f"%{keyword}%"
        
        # Process exclude keywords
        if exclude_keywords:
            for i, keyword in enumerate(exclude_keywords):
                param = f"exclude_kw_{i}"
                if case_sensitive:
                    conditions.append(f"{table_alias}.{text_field} NOT LIKE :{param}")
                else:
                    conditions.append(f"LOWER({table_alias}.{text_field}) NOT LIKE LOWER(:{param})")
                params[param] = f"%{keyword}%"
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        return where_clause, params

    def _build_quality_where_clause(
        self,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        text_field: str = "text",
        table_alias: str = "kb"
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build a WHERE clause for quality metrics filtering.
        """
        conditions = []
        params = {}
        
        if min_length is not None:
            conditions.append(f"CHAR_LENGTH({table_alias}.{text_field}) >= :min_length")
            params['min_length'] = min_length
            
        if max_length is not None:
            conditions.append(f"CHAR_LENGTH({table_alias}.{text_field}) <= :max_length")
            params['max_length'] = max_length
            
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        return where_clause, params

    def filter_by_metadata_db(
        self,
        table_name: str,
        filters: Dict[str, Any],
        query_vector: Optional[List[float]] = None,
        k: int = 10,
        column_name: str = "embedding",
        metric: str = "cosine"
    ) -> List[Dict[str, Any]]:
        """
        Filter results by metadata fields at the database level for improved performance.
        This method performs filtering directly in the database rather than in Python memory.
        """
        try:
            # Build WHERE clause from filters
            where_clause, params = self._build_where_clause(filters)
            
            if query_vector:
                # Perform similarity search with WHERE clause
                results = self.vector_store.similarity_search(
                    table_name=table_name,
                    query_vector=query_vector,
                    k=k,
                    column_name=column_name,
                    metric=metric,
                    where=where_clause,
                    where_params=params
                )
                return results
            else:
                # Perform regular query with WHERE clause
                query = f"SELECT * FROM {table_name} WHERE {where_clause} LIMIT {k}"
                with db.get_session() as session:
                    result = session.execute(text(query), params)
                    rows = [dict(row._mapping) for row in result]
                    return rows
        except Exception as e:
            logger.error(f"Error in database metadata filtering: {e}")
            return []

    def filter_by_date_range_db(
        self,
        table_name: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        date_field: str = "created_at",
        query_vector: Optional[List[float]] = None,
        k: int = 10,
        column_name: str = "embedding",
        metric: str = "cosine"
    ) -> List[Dict[str, Any]]:
        """
        Filter results by date range at the database level for improved performance.
        This method performs filtering directly in the database rather than in Python memory.
        """
        try:
            # Build WHERE clause for date range
            conditions = []
            params = {}
            
            if start_date:
                param_start = f"{date_field}_start"
                conditions.append(f"kb.{date_field} >= :{param_start}")
                params[param_start] = start_date
                
            if end_date:
                param_end = f"{date_field}_end"
                conditions.append(f"kb.{date_field} <= :{param_end}")
                params[param_end] = end_date
                
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            if query_vector:
                # Perform similarity search with WHERE clause
                results = self.vector_store.similarity_search(
                    table_name=table_name,
                    query_vector=query_vector,
                    k=k,
                    column_name=column_name,
                    metric=metric,
                    where=where_clause,
                    where_params=params
                )
                return results
            else:
                # Perform regular query with WHERE clause
                query = f"SELECT * FROM {table_name} WHERE {where_clause} LIMIT {k}"
                with db.get_session() as session:
                    result = session.execute(text(query), params)
                    rows = [dict(row._mapping) for row in result]
                    return rows
        except Exception as e:
            logger.error(f"Error in database date range filtering: {e}")
            return []

    def filter_by_content_db(
        self,
        table_name: str,
        include_keywords: Optional[List[str]] = None,
        exclude_keywords: Optional[List[str]] = None,
        text_field: str = "text",
        case_sensitive: bool = False,
        query_vector: Optional[List[float]] = None,
        k: int = 10,
        column_name: str = "embedding",
        metric: str = "cosine"
    ) -> List[Dict[str, Any]]:
        """
        Filter results by content keywords at the database level for improved performance.
        This method performs filtering directly in the database rather than in Python memory.
        """
        try:
            # Build WHERE clause for content
            where_clause, params = self._build_content_where_clause(
                include_keywords, exclude_keywords, text_field, case_sensitive
            )
            
            if query_vector:
                # Perform similarity search with WHERE clause
                results = self.vector_store.similarity_search(
                    table_name=table_name,
                    query_vector=query_vector,
                    k=k,
                    column_name=column_name,
                    metric=metric,
                    where=where_clause,
                    where_params=params
                )
                return results
            else:
                # Perform regular query with WHERE clause
                query = f"SELECT * FROM {table_name} WHERE {where_clause} LIMIT {k}"
                with db.get_session() as session:
                    result = session.execute(text(query), params)
                    rows = [dict(row._mapping) for row in result]
                    return rows
        except Exception as e:
            logger.error(f"Error in database content filtering: {e}")
            return []

    def filter_by_quality_db(
        self,
        table_name: str,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        text_field: str = "text",
        query_vector: Optional[List[float]] = None,
        k: int = 10,
        column_name: str = "embedding",
        metric: str = "cosine"
    ) -> List[Dict[str, Any]]:
        """
        Filter results by quality metrics at the database level for improved performance.
        This method performs filtering directly in the database rather than in Python memory.
        Note: min_score is not included here as it's a relevance score that applies to similarity search results
        and would typically be applied after the similarity search is performed.
        """
        try:
            # Build WHERE clause for quality
            where_clause, params = self._build_quality_where_clause(
                min_length, max_length, text_field
            )
            
            if query_vector:
                # Perform similarity search with WHERE clause
                results = self.vector_store.similarity_search(
                    table_name=table_name,
                    query_vector=query_vector,
                    k=k,
                    column_name=column_name,
                    metric=metric,
                    where=where_clause,
                    where_params=params
                )
                return results
            else:
                # Perform regular query with WHERE clause
                query = f"SELECT * FROM {table_name} WHERE {where_clause} LIMIT {k}"
                with db.get_session() as session:
                    result = session.execute(text(query), params)
                    rows = [dict(row._mapping) for row in result]
                    return rows
        except Exception as e:
            logger.error(f"Error in database quality filtering: {e}")
            return []

    def apply_multiple_filters_db(
        self,
        table_name: str,
        query_vector: Optional[List[float]] = None,
        k: int = 10,
        column_name: str = "embedding",
        metric: str = "cosine",
        metadata_filters: Optional[Dict[str, Any]] = None,
        date_range: Optional[Tuple[Optional[datetime], Optional[datetime]]] = None,
        quality_filters: Optional[Dict[str, Any]] = None,
        content_filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Apply multiple filters at the database level during query for improved performance.
        This method performs filtering directly in the database rather than in Python memory.
        """
        try:
            all_conditions = []
            all_params = {}
            
            # Build metadata filter WHERE clause
            if metadata_filters:
                where_clause, params = self._build_where_clause(metadata_filters)
                all_conditions.append(where_clause)
                all_params.update(params)
            
            # Build date range filter WHERE clause
            if date_range:
                start_date, end_date = date_range
                conditions = []
                params = {}
                if start_date:
                    param_start = f"created_at_start"
                    conditions.append(f"kb.created_at >= :{param_start}")
                    params[param_start] = start_date
                if end_date:
                    param_end = f"created_at_end"
                    conditions.append(f"kb.created_at <= :{param_end}")
                    params[param_end] = end_date
                date_where_clause = " AND ".join(conditions) if conditions else "1=1"
                all_conditions.append(date_where_clause)
                all_params.update(params)
            
            # Build quality filter WHERE clause
            if quality_filters:
                min_length = quality_filters.get('min_length')
                max_length = quality_filters.get('max_length')
                text_field = quality_filters.get('text_field', 'text')
                where_clause, params = self._build_quality_where_clause(
                    min_length, max_length, text_field
                )
                all_conditions.append(where_clause)
                all_params.update(params)
            
            # Build content filter WHERE clause
            if content_filters:
                include_keywords = content_filters.get('include_keywords')
                exclude_keywords = content_filters.get('exclude_keywords')
                text_field = content_filters.get('text_field', 'text')
                case_sensitive = content_filters.get('case_sensitive', False)
                where_clause, params = self._build_content_where_clause(
                    include_keywords, exclude_keywords, text_field, case_sensitive
                )
                all_conditions.append(where_clause)
                all_params.update(params)
            
            # Combine all conditions
            final_where_clause = " AND ".join(all_conditions) if all_conditions else "1=1"
            
            if query_vector:
                # Perform similarity search with combined WHERE clause
                results = self.vector_store.similarity_search(
                    table_name=table_name,
                    query_vector=query_vector,
                    k=k,
                    column_name=column_name,
                    metric=metric,
                    where=final_where_clause,
                    where_params=all_params
                )
                return results
            else:
                # Perform regular query with combined WHERE clause
                query = f"SELECT * FROM {table_name} WHERE {final_where_clause} LIMIT {k}"
                with db.get_session() as session:
                    result = session.execute(text(query), all_params)
                    rows = [dict(row._mapping) for row in result]
                    return rows
        except Exception as e:
            logger.error(f"Error in database multiple filtering: {e}")
            return []
