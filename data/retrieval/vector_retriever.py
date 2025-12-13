"""
Vector-based semantic retrieval using pgvector with LangChain
"""
from typing import List, Dict, Any, Optional
from langchain_postgres import PGVector
from langchain_core.documents import Document
from common.logger import logger
from common.config import configs
from data.database import postgres_db
from data.embeddings import embeddings_manager


class VectorRetriever:
    """
    pgvector-based vector retriever for semantic similarity search (Singleton)

    Uses:
    - PostgreSQL with pgvector extension
    - LangChain PGVector for vector similarity search
    - Cosine similarity metric

    Use cases:
    - Semantic similarity search
    - Finding conceptually similar content
    - Query understanding beyond exact keywords
    """

    _instance: Optional['VectorRetriever'] = None
    _initialized = False

    def __new__(
        cls,
        table_name: str = "nuclei_templates",
        embedding_model_name: Optional[str] = None,
        embed_dim: int = 384,
    ):
        """
        Singleton implementation - ensures only one instance exists

        Args:
            table_name: PostgreSQL table name (only used on first instantiation)
            embedding_model_name: Embedding model (only used on first instantiation)
            embed_dim: Embedding dimension (only used on first instantiation)
        """
        if cls._instance is None:
            cls._instance = super(VectorRetriever, cls).__new__(cls)
        return cls._instance

    def __init__(
        self,
        table_name: str = "nuclei_templates",
        embedding_model_name: Optional[str] = None,
        embed_dim: int = 384,
    ):
        """
        Initialize vector retriever - only runs once due to Singleton

        Args:
            table_name: PostgreSQL table name for vector storage
            embedding_model_name: Embedding model name (not used with LangChain)
            embed_dim: Embedding dimension
        """
        # Only initialize once
        if self._initialized:
            return

        self.table_name = table_name
        self.embed_dim = embed_dim

        # Get embedding model from manager
        logger.debug("Using embedding model from EmbeddingManager")
        self.embedding = embeddings_manager.get_embedding()

        if not self.embedding:
            raise ValueError("No embedding model available from EmbeddingManager")

        # Initialize PostgreSQL connection string
        db_url = postgres_db.engine.url
        self.connection_string = (
            f"postgresql+psycopg://{db_url.username}:{db_url.password}"
            f"@{db_url.host}:{db_url.port}/{db_url.database}"
        )

        # Initialize vector store
        self.vector_store: Optional[PGVector] = None
        self._create_vector_store()

        # Mark as initialized
        VectorRetriever._initialized = True
        logger.debug(f"VectorRetriever singleton initialized for table: {table_name}")

    def _create_vector_store(self) -> None:
        """Create LangChain PGVector connection"""
        try:
            self.vector_store = PGVector(
                embeddings=self.embedding,
                collection_name=self.table_name,
                connection=self.connection_string,
                use_jsonb=True,
            )
            logger.debug(f"PGVector store created for collection: {self.table_name}")
        except Exception as e:
            logger.error(f"Failed to create PGVector store: {e}")
            raise

    def load_index(self) -> None:
        """Load existing index from vector store (no-op for LangChain)"""
        # LangChain PGVector automatically connects to existing collection
        logger.info(f"Vector index ready for collection: {self.table_name}")

    def index_documents(self, documents: List[Dict[str, Any]]) -> None:
        """
        Index documents into pgvector database

        Args:
            documents: List of dicts with keys:
                      - 'text': Document text content
                      - 'metadata': Document metadata
        """
        try:
            logger.info(f"Indexing {len(documents)} documents into vector store...")

            if not self.vector_store:
                raise ValueError("Vector store not initialized")

            # Convert to LangChain Document objects
            langchain_docs = []
            for doc in documents:
                text = doc.get('text', '')
                metadata = doc.get('metadata', {})
                langchain_docs.append(Document(page_content=text, metadata=metadata))

            # Add documents to vector store
            self.vector_store.add_documents(langchain_docs)

            logger.info(f"Successfully indexed {len(documents)} documents")

        except Exception as e:
            logger.error(f"Failed to index documents: {e}")
            raise

    def search(self, query: str, k: int = 10) -> List[Dict[str, Any]]:
        """
        Perform semantic search using pgvector

        Args:
            query: Search query text
            k: Number of results to return

        Returns:
            List of results with format:
            [{
                'id': node_id,
                'text': node_text,
                'metadata': node_metadata,
                'score': similarity_score,
                'source': 'vector'
            }]
        """
        try:
            if not self.vector_store:
                raise ValueError("Vector store not initialized")

            # Perform similarity search with scores
            results_with_scores = self.vector_store.similarity_search_with_score(
                query, k=k
            )

            # Convert to standardized format
            results = []
            for doc, score in results_with_scores:
                # Generate ID from metadata or use hash
                doc_id = doc.metadata.get('id', hash(doc.page_content))

                results.append({
                    'id': str(doc_id),
                    'text': doc.page_content,
                    'metadata': doc.metadata,
                    'score': float(score) if score is not None else 0.0,
                    'source': 'vector'
                })

            logger.debug(f"Vector search returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    def is_ready(self) -> bool:
        """Check if vector store is ready for searching"""
        return self.vector_store is not None

    def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics"""
        return {
            'table_name': self.table_name,
            'embed_dim': self.embed_dim,
            'is_ready': self.is_ready(),
            'backend': 'pgvector (LangChain)',
            'similarity_metric': 'cosine'
        }
