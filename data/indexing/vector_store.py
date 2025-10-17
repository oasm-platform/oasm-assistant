"""
Vector database management using pgvector for RAG system
"""
from typing import List, Optional, Dict, Any
import re
import json
from sqlalchemy import text
from data.database import postgres_db as db
from common.logger import logger
from common.utils.security import validate_identifier


class PgVectorStore:
    """Vector store implementation using PostgreSQL with pgvector extension for RAG system"""

    # SQL identifier validation pattern - only allow alphanumeric and underscore
    _VALID_IDENTIFIER = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

    def __init__(self, dimension: int = 1536, connection_string: Optional[str] = None):
        """
        Initialize vector store
        Args:
            dimension: Dimension of the vectors to store
            connection_string: Optional database connection string
        """
        self.dimension = dimension
        self.connection_string = connection_string
        self.text = text
        self.db = db

        
    def _ensure_vector_extension(self):
        """Ensure pgvector extension is enabled"""
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

        try:
            # Validate identifiers to prevent SQL injection
            validated_table = validate_identifier(table_name, "table name")
            validated_column = validate_identifier(column_name, "column name")

            # Validate index type
            if index_type not in ("hnsw", "ivfflat"):
                raise ValueError(f"Unsupported index type: {index_type}. Must be 'hnsw' or 'ivfflat'")

            with self.db.get_session() as session:
                if index_type == "hnsw":
                    # Create HNSW index for efficient similarity search
                    index_query = self.text(f"""
                        CREATE INDEX IF NOT EXISTS {validated_table}_{validated_column}_hnsw_idx
                        ON {validated_table}
                        USING hnsw ({validated_column} vector_cosine_ops)
                    """)
                elif index_type == "ivfflat":
                    # Create IVFFlat index (good for larger datasets)
                    index_query = self.text(f"""
                        CREATE INDEX IF NOT EXISTS {validated_table}_{validated_column}_ivfflat_idx
                        ON {validated_table}
                        USING ivfflat ({validated_column} vector_cosine_ops)
                    """)

                session.execute(index_query)
                session.commit()
                logger.info(f"Created {index_type} index on {validated_table}.{validated_column}")
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

        try:
            # Validate table name to prevent SQL injection
            validated_table = validate_identifier(table_name, "table name")

            with self.db.get_session() as session:
                # Default schema with embedding column
                columns = [f"embedding vector({self.dimension})"]
                if schema:
                    # Validate all column names
                    for col_name, col_type in schema.items():
                        validated_col = validate_identifier(col_name, "column name")
                        # Note: col_type is not validated as it's a SQL type definition
                        # In production, you might want to whitelist allowed types
                        columns.append(f"{validated_col} {col_type}")
                else:
                    # Add default columns if no schema provided
                    columns.extend([
                        "id SERIAL PRIMARY KEY",
                        "content TEXT",
                        "metadata JSONB DEFAULT '{}'"
                    ])

                query = self.text(f"""
                    CREATE TABLE IF NOT EXISTS {validated_table} (
                        {', '.join(columns)}
                    )
                """)
                session.execute(query)
                session.commit()
                logger.info(f"Created table {validated_table} with vector column")
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
            
        try:
            # Validate identifiers to prevent SQL injection
            validated_table = validate_identifier(table_name, "table name")
            validated_content_column = validate_identifier(content_column, "column name")
            
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
                        INSERT INTO {validated_table} (embedding, {validated_content_column}, metadata)
                        VALUES ('{vector_str}'::vector, :content, :metadata)
                    """)
                    session.execute(query, {"content": content, "metadata": meta_json})
                
                session.commit()
                logger.info(f"Stored {len(vectors)} vectors in {validated_table}")
        except Exception as e:
            logger.error(f"Failed to store vectors: {e}")
            raise
            
    def query(self, query: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Execute a custom query against the database
        
        Args:
            query: SQL query string with named placeholders (e.g., :my_param)
            params: Dictionary of parameters to substitute in the query.
            
        Returns:
            List of rows as dictionaries
        """
            
        try:
            with self.db.get_session() as session:
                result = session.execute(self.text(query), params or {})
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
            
        try:
            with self.db.get_session() as session:
                session.execute(self.text(sql))
                session.commit()
        except Exception as e:
            logger.error(f"Failed to execute SQL: {e}")
            raise
            
    def similarity_search(self, table_name: str, query_vector: List[float],
                         k: int = 10, column_name: str = "embedding",
                         metric: str = "cosine", where: Optional[str] = None,
                         where_params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Perform similarity search using vector distance/similarity

        Args:
            table_name: Name of the table to search
            query_vector: Query vector
            k: Number of results to return
            column_name: Name of the vector column (default: "embedding")
            metric: Distance metric ('cosine', 'l2', 'ip')
            where: Optional WHERE clause to filter results (use parameterized format like "col = :param")
            where_params: Optional parameters for WHERE clause (use with parameterized where)

        Returns:
            List of result dictionaries with all columns from the table
        """
            
        try:
            # Validate identifiers to prevent SQL injection
            validated_table = validate_identifier(table_name, "table name")
            validated_column = validate_identifier(column_name, "column name")
            
            # Ensure vector is the right dimension
            if len(query_vector) != self.dimension:
                raise ValueError(f"Query vector dimension mismatch: expected {self.dimension}, got {len(query_vector)}")
            
            # Convert query vector to PostgreSQL array format
            vector_str = str(query_vector).replace('[', '{').replace(']', '}')
            
            # Select all columns from table and add distance/similarity
            where_clause = f"WHERE {where}" if where else ""

            # Prepare query based on metric
            if metric == "cosine":
                query = self.text(f"""
                    SELECT *, (1 - ({validated_column} <=> '{vector_str}'::vector)) AS similarity
                    FROM {validated_table}
                    {where_clause}
                    ORDER BY {validated_column} <=> '{vector_str}'::vector
                    LIMIT {k}
                """)
            elif metric == "l2":
                query = self.text(f"""
                    SELECT *, ({validated_column} <-> '{vector_str}'::vector) AS distance
                    FROM {validated_table}
                    {where_clause}
                    ORDER BY {validated_column} <-> '{vector_str}'::vector
                    LIMIT {k}
                """)
            elif metric == "ip":
                query = self.text(f"""
                    SELECT *, ({validated_column} <#> '{vector_str}'::vector) AS distance
                    FROM {validated_table}
                    {where_clause}
                    ORDER BY {validated_column} <#> '{vector_str}'::vector
                    LIMIT {k}
                """)
            else:
                raise ValueError(f"Unsupported metric: {metric}")

            # Execute query with parameters if provided
            with self.db.get_session() as session:
                if where_params:
                    result = session.execute(query, where_params)
                else:
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
