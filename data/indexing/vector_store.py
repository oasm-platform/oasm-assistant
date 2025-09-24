"""
Vector database management using pgvector
"""
from typing import List, Tuple, Optional, Dict, Any
import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session
from data.database import db
from common.logger import logger


class PgVectorStore:
    """Vector store implementation using PostgreSQL with pgvector extension"""
    
    def __init__(self, dimension: int = 1536):
        """
        Initialize vector store
        Args:
            dimension: Dimension of the vectors to store
        """
        self.dimension = dimension
        self._ensure_vector_extension()
        
    def _ensure_vector_extension(self):
        """Ensure pgvector extension is enabled"""
        try:
            with db.get_session() as session:
                session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                session.commit()
                logger.info("pgvector extension ensured")
        except Exception as e:
            logger.error(f"Failed to ensure pgvector extension: {e}")
            
    def create_vector_index(self, table_name: str, column_name: str = "embedding"):
        """
        Create an index for vector similarity search
        
        Args:
            table_name: Name of the table
            column_name: Name of the vector column (default: "embedding")
        """
        try:
            with db.get_session() as session:
                # Create HNSW index for efficient similarity search
                index_query = text(f"""
                    CREATE INDEX IF NOT EXISTS {table_name}_{column_name}_hnsw_idx 
                    ON {table_name} 
                    USING hnsw ({column_name} vector_l2_ops)
                """)
                session.execute(index_query)
                session.commit()
                logger.info(f"Created HNSW index on {table_name}.{column_name}")
        except Exception as e:
            logger.error(f"Failed to create vector index: {e}")
            
    def store_vectors(self, table_name: str, vectors: List[List[float]], 
                     metadata: List[Dict[str, Any]] = None):
        """
        Store vectors in the database
        
        Args:
            table_name: Name of the table to store vectors
            vectors: List of vectors to store
            metadata: Optional metadata for each vector
        """
        try:
            with db.get_session() as session:
                for i, vector in enumerate(vectors):
                    meta = metadata[i] if metadata and i < len(metadata) else {}
                    
                    # Convert vector to PostgreSQL array format
                    vector_str = str(vector).replace('[', '{').replace(']', '}')
                    
                    # Insert vector and metadata
                    columns = ["embedding"]
                    values = [f"'{vector_str}'::vector"]
                    
                    # Add metadata columns
                    for key, value in meta.items():
                        columns.append(key)
                        values.append(f"'{value}'" if isinstance(value, str) else str(value))
                    
                    query = text(f"""
                        INSERT INTO {table_name} ({', '.join(columns)})
                        VALUES ({', '.join(values)})
                    """)
                    session.execute(query)
                
                session.commit()
                logger.info(f"Stored {len(vectors)} vectors in {table_name}")
        except Exception as e:
            logger.error(f"Failed to store vectors: {e}")
            raise
            
    def similarity_search(self, table_name: str, query_vector: List[float], 
                         k: int = 10, column_name: str = "embedding") -> List[Tuple[List[float], float, Dict[str, Any]]]:
        """
        Perform similarity search using vector distance
        
        Args:
            table_name: Name of the table to search
            query_vector: Query vector
            k: Number of results to return
            column_name: Name of the vector column (default: "embedding")
            
        Returns:
            List of (vector, distance, metadata) tuples
        """
        try:
            with db.get_session() as session:
                # Convert query vector to PostgreSQL array format
                vector_str = str(query_vector).replace('[', '{').replace(']', '}')
                
                # Perform similarity search using L2 distance
                query = text(f"""
                    SELECT *, {column_name} <-> '{vector_str}'::vector AS distance
                    FROM {table_name}
                    ORDER BY {column_name} <-> '{vector_str}'::vector
                    LIMIT {k}
                """)
                
                result = session.execute(query)
                matches = []
                for row in result:
                    # Convert row to dict
                    row_dict = dict(row._mapping)
                    # Extract vector, distance and metadata
                    vector = row_dict.get(column_name)
                    distance = row_dict.get('distance')
                    # Remove vector and distance from metadata
                    row_dict.pop(column_name, None)
                    row_dict.pop('distance', None)
                    matches.append((vector, distance, row_dict))
                
                return matches
        except Exception as e:
            logger.error(f"Failed to perform similarity search: {e}")
            raise
            
    def cosine_similarity_search(self, table_name: str, query_vector: List[float], 
                                k: int = 10, column_name: str = "embedding") -> List[Tuple[List[float], float, Dict[str, Any]]]:
        """
        Perform similarity search using cosine similarity
        
        Args:
            table_name: Name of the table to search
            query_vector: Query vector
            k: Number of results to return
            column_name: Name of the vector column (default: "embedding")
            
        Returns:
            List of (vector, similarity, metadata) tuples
        """
        try:
            with db.get_session() as session:
                # Convert query vector to PostgreSQL array format
                vector_str = str(query_vector).replace('[', '{').replace(']', '}')
                
                # Perform similarity search using cosine distance
                query = text(f"""
                    SELECT *, 1 - ({column_name} <=> '{vector_str}'::vector) AS similarity
                    FROM {table_name}
                    ORDER BY {column_name} <=> '{vector_str}'::vector
                    LIMIT {k}
                """)
                
                result = session.execute(query)
                matches = []
                for row in result:
                    # Convert row to dict
                    row_dict = dict(row._mapping)
                    # Extract vector, similarity and metadata
                    vector = row_dict.get(column_name)
                    similarity = row_dict.get('similarity')
                    # Remove vector and similarity from metadata
                    row_dict.pop(column_name, None)
                    row_dict.pop('similarity', None)
                    matches.append((vector, similarity, row_dict))
                
                return matches
        except Exception as e:
            logger.error(f"Failed to perform cosine similarity search: {e}")
            raise
