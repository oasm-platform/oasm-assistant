"""
Vector database management using pgvector for RAG system
"""
from typing import List, Tuple, Optional, Dict, Any
import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session
from data.database import postgres_db as db
from common.logger import logger
import json
import sys


class PgVectorStore:
    """Vector store implementation using PostgreSQL with pgvector extension for RAG system"""
    
    def __init__(self, dimension: int = 1536, connection_string: Optional[str] = None):
        """
        Initialize vector store
        Args:
            dimension: Dimension of the vectors to store
            connection_string: Optional database connection string
        """
        self.dimension = dimension
        self.connection_string = connection_string
        self._sqlalchemy_available = self._check_sqlalchemy()
        self._db_module_available = self._check_db_module()
        if self._sqlalchemy_available:
            try:
                from sqlalchemy import text
                self.text = text
            except ImportError:
                self._sqlalchemy_available = False
        if self._db_module_available:
            try:
                from data.database import db
                self.db = db
            except ImportError:
                self._db_module_available = False

    def _check_sqlalchemy(self):
        try:
            import sqlalchemy
            return True
        except ImportError:
            logger.warning("sqlalchemy is not available, using mock functionality")
            return False

    def _check_db_module(self):
        try:
            from data.database import db
            return True
        except ImportError:
            logger.warning("data.database module is not available, using mock functionality")
            return False

    def _ensure_dependencies(self):
        if not self._sqlalchemy_available or not self._db_module_available:
            logger.warning("Missing dependencies (sqlalchemy or data.database), functionality may be limited")
            return False
        return True
        
    def _ensure_vector_extension(self):
        """Ensure pgvector extension is enabled"""
        if not self._ensure_dependencies():
            logger.warning("Cannot ensure vector extension: missing dependencies")
            return
            
        try:
            with self.db.get_session() as session:
                session.execute(self.text("CREATE EXTENSION IF NOT EXISTS vector"))
                session.commit()
                logger.info("pgvector extension ensured")
        except Exception as e:
            logger.error(f"Failed to ensure pgvector extension: {e}")
            
    def create_vector_index(self, table_name: str, column_name: str = "embedding", index_type: str = "hnsw"):
        """
        Create an index for vector similarity search
        
        Args:
            table_name: Name of the table
            column_name: Name of the vector column (default: "embedding")
            index_type: Type of index ('hnsw' or 'ivfflat', default: 'hnsw')
        """
        if not self._ensure_dependencies():
            logger.warning("Cannot create vector index: missing dependencies")
            return
            
        try:
            with self.db.get_session() as session:
                if index_type == "hnsw":
                    # Create HNSW index for efficient similarity search
                    index_query = self.text(f"""
                        CREATE INDEX IF NOT EXISTS {table_name}_{column_name}_hnsw_idx
                        ON {table_name}
                        USING hnsw ({column_name} vector_cosine_ops)
                    """)
                elif index_type == "ivfflat":
                    # Create IVFFlat index (good for larger datasets)
                    index_query = self.text(f"""
                        CREATE INDEX IF NOT EXISTS {table_name}_{column_name}_ivfflat_idx
                        ON {table_name}
                        USING ivfflat ({column_name} vector_cosine_ops)
                    """)
                else:
                    raise ValueError(f"Unsupported index type: {index_type}")
                    
                session.execute(index_query)
                session.commit()
                logger.info(f"Created {index_type} index on {table_name}.{column_name}")
        except Exception as e:
            logger.error(f"Failed to create vector index: {e}")
            
    def create_table(self, table_name: str, schema: Dict[str, str] = None):
        """
        Create a table with vector column and optional metadata columns
        
        Args:
            table_name: Name of the table to create
            schema: Optional schema definition with column names and types
                   Example: {"content": "TEXT", "title": "TEXT", "category": "TEXT"}
        """
        if not self._ensure_dependencies():
            logger.warning("Cannot create table: missing dependencies")
            return
            
        try:
            with self.db.get_session() as session:
                # Default schema with embedding column
                columns = [f"embedding vector({self.dimension})"]
                if schema:
                    for col_name, col_type in schema.items():
                        columns.append(f"{col_name} {col_type}")
                else:
                    # Add default columns if no schema provided
                    columns.extend([
                        "id SERIAL PRIMARY KEY",
                        "content TEXT",
                        "metadata JSONB DEFAULT '{}'"
                    ])
                
                query = self.text(f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        {', '.join(columns)}
                    )
                """)
                session.execute(query)
                session.commit()
                logger.info(f"Created table {table_name} with vector column")
        except Exception as e:
            logger.error(f"Failed to create table: {e}")
            raise
    
    def store_vectors(self, table_name: str, vectors: List[List[float]],
                     metadata: List[Dict[str, Any]] = None, content_column: str = "content"):
        """
        Store vectors in the database with metadata
        
        Args:
            table_name: Name of the table to store vectors
            vectors: List of vectors to store
            metadata: Optional metadata for each vector
            content_column: Name of the content column (default: "content")
        """
        if not self._ensure_dependencies():
            logger.warning("Cannot store vectors: missing dependencies")
            return
            
        try:
            with self.db.get_session() as session:
                for i, vector in enumerate(vectors):
                    # Ensure vector is the right dimension
                    if len(vector) != self.dimension:
                        raise ValueError(f"Vector dimension mismatch: expected {self.dimension}, got {len(vector)}")
                    
                    meta = metadata[i] if metadata and i < len(metadata) else {}
                    content = meta.get(content_column, "")
                    
                    # Convert vector to PostgreSQL array format
                    vector_str = str(vector).replace('[', '{').replace(']', '}')
                    
                    # Prepare metadata as JSON
                    meta_json = json.dumps({k: v for k, v in meta.items() if k != content_column})
                    
                    # Insert vector and metadata
                    query = self.text(f"""
                        INSERT INTO {table_name} (embedding, {content_column}, metadata)
                        VALUES ('{vector_str}'::vector, :content, :metadata)
                    """)
                    session.execute(query, {"content": content, "metadata": meta_json})
                
                session.commit()
                logger.info(f"Stored {len(vectors)} vectors in {table_name}")
        except Exception as e:
            logger.error(f"Failed to store vectors: {e}")
            raise
            
    def query(self, query: str, params: Optional[List] = None) -> List[Dict[str, Any]]:
        """
        Execute a custom query against the database
        
        Args:
            query: SQL query string with placeholders (e.g., %s)
            params: Parameters to substitute in the query
            
        Returns:
            List of rows as dictionaries
        """
        if not self._ensure_dependencies():
            logger.warning("Cannot execute query: missing dependencies")
            return []
            
        try:
            with self.db.get_session() as session:
                # Replace %s with PostgreSQL placeholders
                query = query.replace('%s', '{}').format(*(['%s'] * query.count('%s')))
                result = session.execute(self.text(query), params or ())
                rows = [dict(row._mapping) for row in result]
                return rows
        except Exception as e:
            logger.error(f"Failed to execute query: {e}")
            raise
    
    def exec_sql(self, sql: str) -> None:
        """
        Execute a raw SQL command
        
        Args:
            sql: SQL command to execute
        """
        if not self._ensure_dependencies():
            logger.warning("Cannot execute SQL: missing dependencies")
            return
            
        try:
            with self.db.get_session() as session:
                session.execute(self.text(sql))
                session.commit()
        except Exception as e:
            logger.error(f"Failed to execute SQL: {e}")
            raise
            
    def similarity_search(self, table_name: str, query_vector: List[float],
                         k: int = 10, column_name: str = "embedding",
                         metric: str = "cosine", where: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Perform similarity search using vector distance/similarity
        
        Args:
            table_name: Name of the table to search
            query_vector: Query vector
            k: Number of results to return
            column_name: Name of the vector column (default: "embedding")
            metric: Distance metric ('cosine', 'l2', 'ip')
            where: Optional WHERE clause to filter results
            
        Returns:
            List of result dictionaries with all columns from the table
        """
        if not self._ensure_dependencies():
            logger.warning("Cannot perform similarity search: missing dependencies")
            return []
            
        try:
            # Ensure vector is the right dimension
            if len(query_vector) != self.dimension:
                raise ValueError(f"Query vector dimension mismatch: expected {self.dimension}, got {len(query_vector)}")
            
            # Convert query vector to PostgreSQL array format
            vector_str = str(query_vector).replace('[', '{').replace(']', '}')
            
            # Select all columns from table and add distance/similarity
            where_clause = f"WHERE {where}" if where else ""
            if metric == "cosine":
                query = self.text(f"""
                    SELECT *, (1 - ({column_name} <=> '{vector_str}'::vector)) AS similarity
                    FROM {table_name}
                    {where_clause}
                    ORDER BY {column_name} <=> '{vector_str}'::vector
                    LIMIT {k}
                """)
            elif metric == "l2":
                query = self.text(f"""
                    SELECT *, ({column_name} <-> '{vector_str}'::vector) AS distance
                    FROM {table_name}
                    {where_clause}
                    ORDER BY {column_name} <-> '{vector_str}'::vector
                    LIMIT {k}
                """)
            elif metric == "ip":
                query = self.text(f"""
                    SELECT *, ({column_name} <#> '{vector_str}'::vector) AS distance
                    FROM {table_name}
                    {where_clause}
                    ORDER BY {column_name} <#> '{vector_str}'::vector
                    LIMIT {k}
                """)
            else:
                raise ValueError(f"Unsupported metric: {metric}")
            
            with self.db.get_session() as session:
                result = session.execute(query)
                matches = [dict(row._mapping) for row in result]
                return matches
        except Exception as e:
            logger.error(f"Failed to perform similarity search: {e}")
            raise

    def batch_similarity_search(self, table_name: str, query_vectors: List[List[float]],
                               k: int = 10, column_name: str = "embedding",
                               metric: str = "cosine", where: Optional[str] = None) -> List[List[Dict[str, Any]]]:
        """
        Perform similarity search for multiple query vectors
        
        Args:
            table_name: Name of the table to search
            query_vectors: List of query vectors
            k: Number of results to return for each query
            column_name: Name of the vector column (default: "embedding")
            metric: Distance metric ('cosine', 'l2', 'ip')
            where: Optional WHERE clause to filter results
            
        Returns:
            List of result lists, one for each query vector
        """
        results = []
        for query_vector in query_vectors:
            results.append(self.similarity_search(
                table_name, query_vector, k, column_name, metric, where
            ))
        return results
