"""
Semantic indexing for RAG system
"""
from typing import List, Dict, Any, Optional, Tuple
from data.indexing.vector_store import PgVectorStore
from data.embeddings.embeddings import Embeddings
from data.indexing.metadata_indexer import MetadataIndexer
from common.logger import logger
import numpy as np


class SemanticIndexer:
    """
    Semantic indexing engine that creates semantic indices for documents to improve
    retrieval quality in the RAG system by understanding meaning beyond keywords.
    """
    
    def __init__(
        self,
        vector_store: Optional[PgVectorStore] = None,
        embedding_model: Optional[Any] = None,
        metadata_indexer: Optional[MetadataIndexer] = None
    ):
        """
        Initialize the semantic indexer.
        
        Args:
            vector_store: PgVectorStore instance for vector storage
            embedding_model: Embedding model for generating semantic representations
            metadata_indexer: Metadata indexer for handling document metadata
        """
        self.vector_store = vector_store or PgVectorStore()
        self.embedding_model = embedding_model or Embeddings.create_embedding('sentence_transformer')
        self.metadata_indexer = metadata_indexer or MetadataIndexer(vector_store=self.vector_store)
    
    def create_semantic_index(
        self,
        content: str,
        doc_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        table_name: str = "semantic_index"
    ) -> bool:
        """
        Create a semantic index for a document by generating embeddings for key concepts
        and storing them in the vector database.
        
        Args:
            content: Document content to create semantic index for
            doc_id: ID of the document
            metadata: Optional metadata for the document
            table_name: Name of the table to store semantic embeddings
            
        Returns:
            True if indexing was successful, False otherwise
        """
        try:
            # Create table with semantic index schema
            self.vector_store.create_table(table_name, {
                "doc_id": "TEXT",
                "concept": "TEXT",
                "embedding": f"vector({self.embedding_model.get_dimension()})",
                "relevance_score": "FLOAT4",
                "metadata": "JSONB",
                "indexed_at": "TIMESTAMP DEFAULT NOW()"
            })
            
            # Extract key concepts from content (simplified approach)
            concepts = self._extract_concepts(content)
            logger.info(f"Extracted {len(concepts)} concepts from document {doc_id}")
            
            # Generate embeddings for concepts
            embeddings = []
            concept_metadata = []
            
            for concept, relevance in concepts:
                embedding = self.embedding_model.embed_text(concept)
                embeddings.append(embedding)
                
                concept_meta = metadata.copy() if metadata else {}
                concept_meta.update({
                    'doc_id': doc_id,
                    'concept': concept,
                    'relevance_score': relevance,
                    'indexed_at': 'NOW()'
                })
                concept_metadata.append(concept_meta)
            
            # Store semantic embeddings
            self.vector_store.store_vectors(
                table_name=table_name,
                vectors=embeddings,
                metadata=concept_metadata
            )
            
            # Index metadata separately for faster filtering
            if metadata:
                self.metadata_indexer.index_metadata(doc_id, metadata)
            
            logger.info(f"Created semantic index for document {doc_id} with {len(concepts)} concepts")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create semantic index for document {doc_id}: {e}")
            return False
    
    def search_semantic(
        self,
        query: str,
        table_name: str = "semantic_index",
        k: int = 10,
        doc_filter: Optional[str] = None
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """
        Search the semantic index for relevant concepts and documents.
        
        Args:
            query: Query text to search for
            table_name: Name of the semantic index table
            k: Number of results to return
            doc_filter: Optional filter for specific document IDs
            
        Returns:
            List of (doc_id, similarity_score, metadata) tuples
        """
        try:
            # Generate embedding for query
            query_embedding = self.embedding_model.embed_query(query)
            
            # Build WHERE clause for document filtering
            where_clause = f"WHERE doc_id = '{doc_filter}'" if doc_filter else ""
            
            # Perform semantic search using vector similarity
            results = self.vector_store.similarity_search(
                table_name=table_name,
                query_vector=query_embedding,
                k=k,
                column_name="embedding",
                metric="cosine",
                where=where_clause
            )
            
            # Format results
            formatted_results = []
            for row in results:
                doc_id = row.get('doc_id', '')
                similarity = row.get('similarity', 0.0)
                metadata = row.get('metadata', {})
                formatted_results.append((doc_id, similarity, metadata))
            
            logger.info(f"Semantic search returned {len(formatted_results)} results")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Failed to perform semantic search: {e}")
            return []
    
    def batch_create_semantic_index(
        self,
        documents: List[Dict[str, Any]],
        table_name: str = "semantic_index"
    ) -> Dict[str, bool]:
        """
        Create semantic indices for multiple documents at once.
        
        Args:
            documents: List of documents with 'content', 'id', and optional 'metadata'
            table_name: Name of the table to store semantic embeddings
            
        Returns:
            Dictionary mapping document IDs to indexing success status
        """
        results = {}
        for doc in documents:
            content = doc.get('content', '')
            doc_id = doc.get('id', '')
            metadata = doc.get('metadata', {})
            results[doc_id] = self.create_semantic_index(content, doc_id, metadata, table_name)
        return results
    
    def update_semantic_index(
        self,
        content: str,
        doc_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        table_name: str = "semantic_index"
    ) -> bool:
        """
        Update the semantic index for an existing document.
        
        Args:
            content: New content for the document
            doc_id: ID of the document to update
            metadata: Optional updated metadata
            table_name: Name of the semantic index table
            
        Returns:
            True if update was successful, False otherwise
        """
        try:
            # Delete existing semantic index for this document if vector store supports DB operations
            if hasattr(self.vector_store, 'db') and hasattr(self.vector_store.db, 'get_session') and hasattr(self.vector_store, 'text'):
                with self.vector_store.db.get_session() as session:
                    delete_query = self.vector_store.text(f"DELETE FROM {table_name} WHERE doc_id = :doc_id")
                    session.execute(delete_query, {"doc_id": doc_id})
                    session.commit()
                    logger.info(f"Deleted existing semantic index for document {doc_id}")
            else:
                logger.warning("Cannot delete semantic index: vector store does not support DB operations")
            
            # Create new semantic index
            return self.create_semantic_index(content, doc_id, metadata, table_name)
        except Exception as e:
            logger.error(f"Failed to update semantic index for document {doc_id}: {e}")
            return False
    
    def _extract_concepts(self, content: str) -> List[Tuple[str, float]]:
        """
        Extract key concepts from content with relevance scores (simplified implementation).
        In a real implementation, this would use NLP techniques like keyword extraction,
        named entity recognition, etc.
        
        Args:
            content: Document content to extract concepts from
            
        Returns:
            List of (concept, relevance_score) tuples
        """
        # Simplified concept extraction - in practice, this would use more sophisticated NLP
        sentences = content.split('.')
        concepts = []
        
        for i, sentence in enumerate(sentences[:10]):  # Limit to first 10 sentences
            # Extract potential concepts (nouns, proper nouns, etc.)
            words = sentence.strip().split()
            for word in words[:5]:  # Limit to first 5 words per sentence
                if len(word) > 3:  # Only consider words longer than 3 characters
                    # Calculate a simple relevance score based on position and frequency
                    relevance = 1.0 / (i + 1)  # Earlier sentences are more relevant
                    concepts.append((word.strip(',;:()'), relevance))
        
        # Remove duplicates while preserving order
        seen = set()
        unique_concepts = []
        for concept, relevance in concepts:
            if concept.lower() not in seen:
                seen.add(concept.lower())
                unique_concepts.append((concept, relevance))
        
        # Sort by relevance (descending)
        unique_concepts.sort(key=lambda x: x[1], reverse=True)
        return unique_concepts[:50] # Return top 50 concepts