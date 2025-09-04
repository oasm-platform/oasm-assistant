"""
ChromaDB utility class for OASM Assistant
"""
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional, Union
import uuid
from chromadb.api.models.Collection import Collection

from common.logger import logger

class ChromaDatabase:
    """Class to handle ChromaDB operations for OASM Assistant"""
    
    def __init__(self, host: str = "localhost", port: int = 8000, 
                 persist_directory: Optional[str] = None):
        """
        Initialize ChromaDB client
        
        Args:
            host: ChromaDB server host
            port: ChromaDB server port
            persist_directory: Directory to persist data (for local mode)
        """
        self.host = host
        self.port = port
        self.persist_directory = persist_directory 
        self.client = None
        self.collections: Dict[str, Collection] = {}
        
        # Initialize client
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """Initialize the ChromaDB client"""
        try:
            if self.persist_directory:
                # Local persistence mode
                self.client = chromadb.PersistentClient(
                    path=self.persist_directory
                )
            else:
                # Client-server mode
                self.client = chromadb.HttpClient(
                    host=self.host,
                    port=self.port,
                    settings=Settings(
                        allow_reset=True,
                        anonymized_telemetry=False
                    )
                )
            self.is_initialized = True

        
        except Exception as e:
            logger.error(f"Error initializing ChromaDB client: {e}")
            self.is_initialized = False
            raise
    
    def create_collection(self, name: str, 
                         metadata: Optional[Dict[str, Any]] = None,
                         embedding_function: Any = None) -> Collection:
        """
        Create a new collection
        
        Args:
            name: Name of the collection
            metadata: Optional metadata for the collection
            embedding_function: Optional custom embedding function
            
        Returns:
            Collection object
        """
        try:
            if embedding_function:
                collection = self.client.create_collection(
                    name=name,
                    metadata=metadata,
                    embedding_function=embedding_function
                )
            else:
                collection = self.client.create_collection(
                    name=name,
                    metadata=metadata
                )
            
            self.collections[name] = collection
            return collection
        except Exception as e:
            logger.error(f"Error creating collection '{name}': {e}")
            raise
    
    def get_collection(self, name: str) -> Collection:
        """
        Get an existing collection
        
        Args:
            name: Name of the collection
            
        Returns:
            Collection object
        """
        if name in self.collections:
            return self.collections[name]
        
        try:
            collection = self.client.get_collection(name=name)
            self.collections[name] = collection
            return collection
        except Exception as e:
            logger.error(f"Error getting collection '{name}': {e}")
            raise
    
    def delete_collection(self, name: str) -> None:
        """
        Delete a collection
        
        Args:
            name: Name of the collection to delete
        """
        try:
            self.client.delete_collection(name=name)
            if name in self.collections:
                del self.collections[name]
            logger.info(f"Collection '{name}' deleted successfully")
        except Exception as e:
            logger.error(f"Error deleting collection '{name}': {e}")
            raise
    
    def list_collections(self) -> List[str]:
        """
        List all collections
        
        Returns:
            List of collection names
        """
        try:
            collections = self.client.list_collections()
            return [collection.name for collection in collections]
        except Exception as e:
            logger.error(f"Error listing collections: {e}")
            raise
    
    def add_documents(self, 
                 collection_name: str,
                 documents: List[str],
                 ids: Optional[List[str]] = None,
                 metadatas: Optional[List[Dict[str, Any]]] = None,
                 embeddings: Optional[List[List[float]]] = None) -> None:
        """
        Add documents to a collection with improved validation
        """
        try:
            collection = self.get_collection(collection_name)
        
            # Generate IDs if not provided
            if ids is None:
                ids = [str(uuid.uuid4()) for _ in range(len(documents))]
        
            # Validate lengths
            if len(ids) != len(documents):
                raise ValueError("Length of ids must match length of documents")
        
            if metadatas and len(metadatas) != len(documents):
                raise ValueError("Length of metadatas must match length of documents")
        
            if embeddings and len(embeddings) != len(documents):
                raise ValueError("Length of embeddings must match length of documents")
        
            # Add documents to collection
            collection.add(
                documents=documents,
                ids=ids,
                metadatas=metadatas,
                embeddings=embeddings
            )
        except Exception as e:
            logger.error(f"Error adding documents to collection '{collection_name}': {e}")
            raise
    
    def query_collection(self, 
                        collection_name: str,
                        query_texts: Union[str, List[str]],
                        n_results: int = 5,
                        where: Optional[Dict[str, Any]] = None,
                        where_document: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Query a collection
        
        Args:
            collection_name: Name of the collection
            query_texts: Query text or list of query texts
            n_results: Number of results to return
            where: Optional metadata filter
            where_document: Optional document content filter
            
        Returns:
            Query results
        """
        try:
            collection = self.get_collection(collection_name)
            
            # Ensure query_texts is a list
            if isinstance(query_texts, str):
                query_texts = [query_texts]
            
            # Perform query
            results = collection.query(
                query_texts=query_texts,
                n_results=n_results,
                where=where,
                where_document=where_document
            )
            
            return results
        except Exception as e:
            logger.error(f"Error querying collection '{collection_name}': {e}")
            raise
    
    def update_documents(self,
                        collection_name: str,
                        ids: List[str],
                        documents: Optional[List[str]] = None,
                        metadatas: Optional[List[Dict[str, Any]]] = None,
                        embeddings: Optional[List[List[float]]] = None) -> None:
        """
        Update documents in a collection
        
        Args:
            collection_name: Name of the collection
            ids: List of document IDs to update
            documents: Optional list of updated document texts
            metadatas: Optional list of updated metadata dictionaries
            embeddings: Optional list of updated embeddings
        """
        try:
            collection = self.get_collection(collection_name)
            
            # Update documents in collection
            collection.update(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings
            )
        except Exception as e:
            logger.error(f"Error updating documents in collection '{collection_name}': {e}")
            raise
    
    def delete_documents(self,
                        collection_name: str,
                        ids: Optional[List[str]] = None,
                        where: Optional[Dict[str, Any]] = None,
                        where_document: Optional[Dict[str, Any]] = None) -> None:
        """
        Delete documents from a collection
        
        Args:
            collection_name: Name of the collection
            ids: Optional list of document IDs to delete
            where: Optional metadata filter
            where_document: Optional document content filter
        """
        try:
            collection = self.get_collection(collection_name)
            
            # Delete documents from collection
            collection.delete(
                ids=ids,
                where=where,
                where_document=where_document
            )
        except Exception as e:
            logger.error(f"Error deleting documents from collection '{collection_name}': {e}")
            raise
    
    def get_document_count(self, collection_name: str) -> int:
        """
        Get the number of documents in a collection
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            Number of documents
        """
        try:
            collection = self.get_collection(collection_name)
            return collection.count()
        except Exception as e:
            logger.error(f"Error getting document count for collection '{collection_name}': {e}")
            raise
    
    def reset_database(self) -> None:
        """Reset the entire database"""
        try:
            self.client.reset()
            self.collections.clear()
            logger.info("ChromaDB has been reset")
        except Exception as e:
            logger.error(f"Error resetting database: {e}")
            raise
    
    def close(self) -> None:
        """Close the database connection"""
        self.collections.clear()
        self.client = None

    async def health_check(self) -> bool:
        """
        Check the health of the database with detailed logging
        """
        logger.info("Starting ChromaDB health check...")
        
        # Check if client is initialized
        if not self.is_initialized or self.client is None:
            logger.error("ChromaDB client is not initialized")
            return False
        
        try:
            self.client.list_collections()
            try:
                self.client.heartbeat()
            except AttributeError:
                logger.info("ChromaDB heartbeat method not available (normal for some versions)")
            except Exception as e:
                logger.warning(f"ChromaDB heartbeat failed: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"ChromaDB health check failed: {e}")
            logger.error(f"Client type: {type(self.client)}")
            logger.error(f"Host: {self.host}, Port: {self.port}, Persist dir: {self.persist_directory}")
            return False
