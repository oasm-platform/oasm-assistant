"""
Metadata indexing for RAG system
"""
from typing import List, Dict, Any, Optional
from data.indexing.vector_store import PgVectorStore
from common.logger import logger
import json
from datetime import datetime
from common.utils.security import validate_identifier


class MetadataIndexer:
    """
    Metadata indexing engine that handles indexing and querying of document metadata
    for the RAG system to improve search relevance and filtering capabilities.
    """

    def __init__(
        self,
        vector_store: Optional[PgVectorStore] = None
    ):
        """
        Initialize the metadata indexer.

        Args:
            vector_store: PgVectorStore instance for database operations
        """
        self.vector_store = vector_store or PgVectorStore()
    
    def index_metadata(
        self,
        doc_id: str,
        metadata: Dict[str, Any],
        table_name: str = "metadata_index"
    ) -> bool:
        """
        Index metadata for a document in a dedicated metadata table.

        Args:
            doc_id: ID of the document
            metadata: Metadata dictionary to index
            table_name: Name of the table to store metadata

        Returns:
            True if indexing was successful, False otherwise
        """
        try:
            # Validate table name to prevent SQL injection
            validated_table_name = validate_identifier(table_name, "table name")

            # Create table if it doesn't exist
            if hasattr(self.vector_store, 'create_table'):
                self.vector_store.create_table(validated_table_name, {
                    "doc_id": "TEXT PRIMARY KEY",
                    "metadata": "JSONB",
                    "indexed_at": "TIMESTAMP DEFAULT NOW()",
                    "tags": "TEXT[]",
                    "category": "TEXT",
                    "source": "TEXT",
                    "created_date": "DATE",
                    "updated_date": "DATE"
                })
            else:
                logger.warning("Cannot create table: vector store does not support table creation")
            
            # Prepare metadata values
            prepared_metadata = self._prepare_metadata(metadata)
            tags = prepared_metadata.get('tags', [])
            category = prepared_metadata.get('category', '')
            source = prepared_metadata.get('source', '')
            created_date = prepared_metadata.get('created_date', datetime.now().date())
            updated_date = prepared_metadata.get('updated_date', datetime.now().date())
            
            # Insert or update metadata record if vector store supports SQL execution
            if hasattr(self.vector_store, 'text') and hasattr(self.vector_store, 'exec_sql'):
                query = f"""
                    INSERT INTO {validated_table_name} (doc_id, metadata, tags, category, source, created_date, updated_date)
                    VALUES (:doc_id, :metadata, :tags, :category, :source, :created_date, :updated_date)
                    ON CONFLICT (doc_id) DO UPDATE SET
                        metadata = :metadata,
                        tags = :tags,
                        category = :category,
                        source = :source,
                        updated_date = :updated_date
                """
                self.vector_store.exec_sql(query, {
                    "doc_id": doc_id,
                    "metadata": json.dumps(prepared_metadata),
                    "tags": tags,  # Pass tags list directly - let the database driver handle formatting
                    "category": category,
                    "source": source,
                    "created_date": created_date,
                    "updated_date": updated_date
                })
            else:
                logger.warning("Cannot execute SQL: vector store does not support SQL execution")
                return False
            
            logger.info(f"Indexed metadata for document {doc_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to index metadata for document {doc_id}: {e}")
            return False
    
    def index_batch_metadata(
        self,
        documents_metadata: List[Dict[str, Any]],
        table_name: str = "metadata_index"
    ) -> Dict[str, bool]:
        """
        Index metadata for multiple documents at once.
        
        Args:
            documents_metadata: List of dictionaries with 'doc_id' and 'metadata'
            table_name: Name of the table to store metadata
            
        Returns:
            Dictionary mapping document IDs to indexing success status
        """
        results = {}
        for doc_meta in documents_metadata:
            doc_id = doc_meta.get('doc_id')
            metadata = doc_meta.get('metadata', {})
            results[doc_id] = self.index_metadata(doc_id, metadata, table_name)
        return results
    
    def query_metadata(
        self,
        filters: Optional[Dict[str, Any]] = None,
        table_name: str = "metadata_index",
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Query metadata based on filters.

        Args:
            filters: Dictionary of filter conditions
            table_name: Name of the metadata table
            limit: Maximum number of results to return

        Returns:
            List of matching metadata records
        """
        try:
            # Validate table name to prevent SQL injection
            validated_table_name = validate_identifier(table_name, "table name")

            # Validate limit parameter
            if limit is not None:
                if not isinstance(limit, int) or limit < 0:
                    raise ValueError("Limit must be a non-negative integer")
                if limit > 10000:  # Reasonable upper bound
                    raise ValueError("Limit too large (max 10000)")

            # Build WHERE clause from filters
            where_clauses = []
            params = {}
            
            if filters:
                for key, value in filters.items():
                    if key == "tags":
                        # Handle array tags
                        if isinstance(value, list):
                            where_clauses.append("tags && :tags")
                            params["tags"] = value  # Pass tags list directly - let the database driver handle formatting
                        else:
                            where_clauses.append("tags @> ARRAY[:tag]")
                            params["tag"] = value
                    elif key == "date_range":
                        # Handle date range
                        if isinstance(value, dict) and "start" in value and "end" in value:
                            where_clauses.append("created_date BETWEEN :start_date AND :end_date")
                            params["start_date"] = value["start"]
                            params["end_date"] = value["end"]
                    elif key in ["category", "source"]:
                        # Handle exact matches
                        where_clauses.append(f"{key} = :{key}")
                        params[key] = value
                    else:
                        # Handle other fields as JSONB queries
                        where_clauses.append(f"metadata @> :{key}_json")
                        params[f"{key}_json"] = json.dumps({key: value})
            
            # Build query
            where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
            # Use parameterized limit for safety
            limit_clause = f"LIMIT {int(limit)}" if limit else ""

            query = f"""
                SELECT doc_id, metadata, tags, category, source, created_date, updated_date
                FROM {validated_table_name}
                {where_clause}
                ORDER BY indexed_at DESC
                {limit_clause}
            """
            
            results = self.vector_store.query(query, params)
            logger.info(f"Queried metadata with {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Failed to query metadata: {e}")
            return []
    
    def update_metadata(
        self,
        doc_id: str,
        metadata: Dict[str, Any],
        table_name: str = "metadata_index"
    ) -> bool:
        """
        Update metadata for an existing document.
        
        Args:
            doc_id: ID of the document to update
            metadata: New metadata dictionary
            table_name: Name of the metadata table
            
        Returns:
            True if update was successful, False otherwise
        """
        return self.index_metadata(doc_id, metadata, table_name)
    
    def delete_metadata(
        self,
        doc_id: str,
        table_name: str = "metadata_index"
    ) -> bool:
        """
        Delete metadata for a document.

        Args:
            doc_id: ID of the document to delete metadata for
            table_name: Name of the metadata table

        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            # Validate table name to prevent SQL injection
            validated_table_name = validate_identifier(table_name, "table name")

            if hasattr(self.vector_store, 'text') and hasattr(self.vector_store, 'exec_sql'):
                query = f"DELETE FROM {validated_table_name} WHERE doc_id = :doc_id"
                self.vector_store.exec_sql(query, {"doc_id": doc_id})
                logger.info(f"Deleted metadata for document {doc_id}")
                return True
            else:
                logger.warning("Cannot delete metadata: vector store does not support SQL execution")
                return False
        except Exception as e:
            logger.error(f"Failed to delete metadata for document {doc_id}: {e}")
            return False
    
    def _prepare_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare metadata for indexing by extracting and normalizing fields.
        
        Args:
            metadata: Raw metadata dictionary
            
        Returns:
            Prepared metadata dictionary with standardized fields
        """
        prepared = metadata.copy()
        prepared['indexed_at'] = datetime.now().isoformat()
        return prepared
