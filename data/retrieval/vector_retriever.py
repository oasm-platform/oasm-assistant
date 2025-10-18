"""
Vector-based semantic retrieval using HNSW index
"""
from typing import List, Dict, Any, Optional
from llama_index.core import VectorStoreIndex, StorageContext, Settings
from llama_index.core.schema import Document, NodeWithScore
from llama_index.vector_stores.postgres import PGVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core.retrievers import VectorIndexRetriever
from common.logger import logger
from common.config import configs
from data.database import postgres_db


class VectorRetriever:
    """
    HNSW-based vector retriever for semantic similarity search

    Uses:
    - PostgreSQL with pgvector extension
    - HNSW index for efficient similarity search
    - Cosine similarity metric

    Use cases:
    - Semantic similarity search
    - Finding conceptually similar content
    - Query understanding beyond exact keywords
    """

    def __init__(
        self,
        table_name: str = "nuclei_templates",
        embedding_model_name: Optional[str] = None,
        embed_dim: int = 384,
    ):
        """
        Initialize vector retriever

        Args:
            table_name: PostgreSQL table name for vector storage
            embedding_model_name: HuggingFace embedding model name
            embed_dim: Embedding dimension
        """
        self.table_name = table_name
        self.embed_dim = embed_dim

        # Initialize embedding model
        model_name = embedding_model_name or configs.embedding.model_name or "sentence-transformers/all-MiniLM-L6-v2"
        logger.info(f"Initializing embedding model: {model_name}")
        self.embed_model = HuggingFaceEmbedding(model_name=model_name)

        # Set global settings for LlamaIndex
        Settings.embed_model = self.embed_model
        Settings.chunk_size = 512
        Settings.chunk_overlap = 50

        # Initialize PostgreSQL vector store
        self.vector_store = self._create_vector_store()

        # Storage context
        self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)

        # Vector index (will be loaded or created)
        self.index: Optional[VectorStoreIndex] = None

        logger.info(f"VectorRetriever initialized for table: {table_name}")

    def _create_vector_store(self) -> PGVectorStore:
        """Create LlamaIndex PGVectorStore connection"""
        db_url = postgres_db.engine.url

        return PGVectorStore.from_params(
            host=db_url.host,
            port=db_url.port,
            database=db_url.database,
            user=db_url.username,
            password=db_url.password,
            table_name=self.table_name,
            embed_dim=self.embed_dim,
            hnsw_kwargs={
                "hnsw_m": 16,
                "hnsw_ef_construction": 200,
                "hnsw_ef_search": 64,
                "hnsw_dist_method": "vector_cosine_ops",
            }
        )

    def load_index(self) -> VectorStoreIndex:
        """Load existing index from vector store"""
        try:
            logger.info(f"Loading existing vector index from {self.table_name}")
            self.index = VectorStoreIndex.from_vector_store(
                vector_store=self.vector_store,
                storage_context=self.storage_context
            )
            logger.info("Vector index loaded successfully")
            return self.index
        except Exception as e:
            logger.warning(f"Failed to load index: {e}. Creating new index...")
            self.index = VectorStoreIndex([], storage_context=self.storage_context)
            return self.index

    def index_documents(self, documents: List[Dict[str, Any]]) -> None:
        """
        Index documents into HNSW vector index

        Args:
            documents: List of dicts with keys:
                      - 'text': Document text content
                      - 'metadata': Document metadata
        """
        try:
            logger.info(f"Indexing {len(documents)} documents into vector store...")

            # Create LlamaIndex Document objects
            llama_docs = []
            for doc in documents:
                text = doc.get('text', '')
                metadata = doc.get('metadata', {})
                llama_docs.append(Document(text=text, metadata=metadata))

            # Create or update vector index (HNSW)
            if self.index is None:
                self.index = VectorStoreIndex.from_documents(
                    llama_docs,
                    storage_context=self.storage_context
                )
            else:
                # Add documents to existing index
                for doc in llama_docs:
                    self.index.insert(doc)

            logger.info(f"Successfully indexed {len(documents)} documents")

        except Exception as e:
            logger.error(f"Failed to index documents: {e}")
            raise

    def search(self, query: str, k: int = 10) -> List[Dict[str, Any]]:
        """
        Perform semantic search using HNSW vector index

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
            if self.index is None:
                self.load_index()

            # Create retriever
            retriever = VectorIndexRetriever(
                index=self.index,
                similarity_top_k=k,
            )

            # Retrieve nodes
            nodes: List[NodeWithScore] = retriever.retrieve(query)

            # Convert to standardized format
            results = []
            for node in nodes:
                results.append({
                    'id': node.node.id_,
                    'text': node.node.get_content(),
                    'metadata': node.node.metadata,
                    'score': float(node.score) if node.score is not None else 0.0,
                    'source': 'vector'
                })

            logger.debug(f"Vector search returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    def is_ready(self) -> bool:
        """Check if index is ready for searching"""
        return self.index is not None

    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics"""
        return {
            'table_name': self.table_name,
            'embed_dim': self.embed_dim,
            'is_ready': self.is_ready(),
            'index_type': 'HNSW (pgvector)',
            'similarity_metric': 'cosine'
        }
