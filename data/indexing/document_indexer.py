"""
Document indexing engine for RAG system
"""
from typing import List, Dict, Any, Optional
from data.indexing.vector_store import PgVectorStore
from data.embeddings.embeddings import Embeddings
from data.processors.chunk_processor import ChunkProcessor
from common.logger import logger
import hashlib


class DocumentIndexer:
    """
    Document indexing engine that handles document ingestion, chunking, embedding, and storage
    for the RAG system.
    """
    
    def __init__(
        self,
        vector_store: Optional[PgVectorStore] = None,
        embedding_model: Optional[Any] = None,
        chunk_processor: Optional[ChunkProcessor] = None
    ):
        """
        Initialize the document indexer.
        
        Args:
            vector_store: PgVectorStore instance for vector storage
            embedding_model: Embedding model for generating document embeddings
            chunk_processor: Chunk processor for document preprocessing
        """
        self.vector_store = vector_store or PgVectorStore()
        self.embedding_model = embedding_model or Embeddings.create_embedding('sentence_transformer')
        self.chunk_processor = chunk_processor or ChunkProcessor()
    
    def index_document(
        self,
        content: str,
        doc_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        table_name: str = "documents",
        chunk_size: int = 512,
        chunk_overlap: int = 50
    ) -> List[str]:
        """
        Index a single document by chunking, embedding, and storing in vector database.
        
        Args:
            content: Document content as string
            doc_id: Optional document ID (will be generated if not provided)
            metadata: Optional metadata for the document
            table_name: Name of the table to store embeddings
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks
            
        Returns:
            List of IDs of the indexed chunks
        """
        try:
            # Generate document ID if not provided
            if doc_id is None:
                doc_id = hashlib.md5(content.encode()).hexdigest()
            
            # Chunk the document
            chunks = self.chunk_processor.chunk_text(content, chunk_size, chunk_overlap)
            logger.info(f"Chunked document into {len(chunks)} pieces")
            
            # Generate embeddings for chunks
            embeddings = []
            chunk_metadata = []
            
            for i, chunk in enumerate(chunks):
                embedding = self.embedding_model.embed_text(chunk)
                embeddings.append(embedding)
                
                # Create metadata for this chunk
                chunk_meta = metadata.copy() if metadata else {}
                chunk_meta.update({
                    'chunk_id': f"{doc_id}_chunk_{i}",
                    'doc_id': doc_id,
                    'chunk_index': i,
                    'content': chunk,
                    'content_length': len(chunk)
                })
                chunk_metadata.append(chunk_meta)
            
            # Store embeddings in vector database
            self.vector_store.create_table(table_name, {
                "content": "TEXT",
                "doc_id": "TEXT",
                "chunk_id": "TEXT",
                "chunk_index": "INTEGER",
                "metadata": "JSONB"
            })
            
            self.vector_store.store_vectors(
                table_name=table_name,
                vectors=embeddings,
                metadata=chunk_metadata
            )
            
            logger.info(f"Indexed document {doc_id} with {len(chunks)} chunks to {table_name}")
            return [meta['chunk_id'] for meta in chunk_metadata]
            
        except Exception as e:
            logger.error(f"Failed to index document: {e}")
            raise
    
    def index_documents(
        self,
        documents: List[Dict[str, Any]],
        table_name: str = "documents",
        chunk_size: int = 512,
        chunk_overlap: int = 50
    ) -> Dict[str, List[str]]:
        """
        Index multiple documents at once.
        
        Args:
            documents: List of documents, each with 'content' and optional 'id', 'metadata'
            table_name: Name of the table to store embeddings
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks
            
        Returns:
            Dictionary mapping document IDs to lists of indexed chunk IDs
        """
        results = {}
        for doc in documents:
            content = doc.get('content', '')
            doc_id = doc.get('id')
            metadata = doc.get('metadata', {})
            
            chunk_ids = self.index_document(
                content=content,
                doc_id=doc_id,
                metadata=metadata,
                table_name=table_name,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )
            results[doc_id or hashlib.md5(content.encode()).hexdigest()] = chunk_ids
        
        logger.info(f"Indexed {len(documents)} documents")
        return results
    
    def update_document(
        self,
        doc_id: str,
        new_content: str,
        metadata: Optional[Dict[str, Any]] = None,
        table_name: str = "documents",
        chunk_size: int = 512,
        chunk_overlap: int = 50
    ) -> List[str]:
        """
        Update an existing document by deleting old chunks and indexing new ones.
        
        Args:
            doc_id: ID of the document to update
            new_content: New content for the document
            metadata: Optional updated metadata
            table_name: Name of the table storing embeddings
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks
            
        Returns:
            List of IDs of the newly indexed chunks
        """
        try:
            # Delete existing document chunks if vector store supports DB operations
            if hasattr(self.vector_store, 'db') and hasattr(self.vector_store.db, 'get_session') and hasattr(self.vector_store, 'text'):
                with self.vector_store.db.get_session() as session:
                    delete_query = self.vector_store.text(f"DELETE FROM {table_name} WHERE doc_id = :doc_id")
                    session.execute(delete_query, {"doc_id": doc_id})
                    session.commit()
                    logger.info(f"Deleted old chunks for document {doc_id}")
            else:
                logger.warning("Cannot delete old document chunks: vector store does not support DB operations")
            
            # Index the new content
            return self.index_document(
                content=new_content,
                doc_id=doc_id,
                metadata=metadata,
                table_name=table_name,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )
        except Exception as e:
            logger.error(f"Failed to update document {doc_id}: {e}")
            raise
    
    def delete_document(self, doc_id: str, table_name: str = "documents") -> bool:
        """
        Delete all chunks associated with a document.
        
        Args:
            doc_id: ID of the document to delete
            table_name: Name of the table storing embeddings
            
        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            if hasattr(self.vector_store, 'db') and hasattr(self.vector_store.db, 'get_session') and hasattr(self.vector_store, 'text'):
                with self.vector_store.db.get_session() as session:
                    delete_query = self.vector_store.text(f"DELETE FROM {table_name} WHERE doc_id = :doc_id")
                    result = session.execute(delete_query, {"doc_id": doc_id})
                    session.commit()
                    logger.info(f"Deleted {result.rowcount} chunks for document {doc_id}")
                    return True
            else:
                logger.warning("Cannot delete document: vector store does not support DB operations")
                return False
        except Exception as e:
            logger.error(f"Failed to delete document {doc_id}: {e}")
            return False
