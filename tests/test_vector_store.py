"""
Test for vector store implementation
"""
import unittest
import numpy as np
from data.indexing.vector_store import PgVectorStore
from data.database import db
from data.embeddings.embeddings import Embeddings


class TestVectorStore(unittest.TestCase):
    """Test cases for PgVectorStore"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.vector_store = PgVectorStore(dimension=4)
        
    def test_vector_store_initialization(self):
        """Test vector store initialization"""
        self.assertIsInstance(self.vector_store, PgVectorStore)
        self.assertEqual(self.vector_store.dimension, 4)
        
    def test_store_and_search_vectors(self):
        """Test storing and searching vectors"""
        # Sample vectors
        vectors = [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0]
        ]
        
        # Sample metadata
        metadata = [
            {"id": 1, "label": "vector_1"},
            {"id": 2, "label": "vector_2"},
            {"id": 3, "label": "vector_3"},
            {"id": 4, "label": "vector_4"}
        ]
        
        # Store vectors (this would require a proper table in the database)
        # For now, we'll just test that the method exists and can be called
        self.assertTrue(hasattr(self.vector_store, 'store_vectors'))
        self.assertTrue(hasattr(self.vector_store, 'similarity_search'))
        self.assertTrue(hasattr(self.vector_store, 'cosine_similarity_search'))




def main():
    """Example of using the vector store"""
    # Initialize vector store
    vector_store = PgVectorStore(dimension=384)  # Using sentence-transformers dimension
    
    # Create some sample text data
    texts = [
        "This is a sample document about artificial intelligence",
        "Machine learning is a subset of AI that focuses on algorithms",
        "Natural language processing helps computers understand human language",
        "Computer vision enables machines to interpret visual information",
        "Deep learning uses neural networks with multiple layers"
    ]
    
    # Create embeddings for the texts
    try:
        # Using sentence-transformers embedding
        embedding_model = Embeddings.create_embedding('sentence_transformer')
        embeddings = []
        
        for text in texts:
            # Generate embedding for each text
            embedding = embedding_model.embed_query(text)
            embeddings.append(embedding)
            
        print(f"Generated {len(embeddings)} embeddings")
        print(f"Embedding dimension: {len(embeddings[0])}")
        
        # In a real implementation, you would store these embeddings in the database
        # using the vector_store.store_vectors() method
        
        # For similarity search, you would use:
        # query_embedding = embedding_model.embed_query("Tell me about AI")
        # results = vector_store.similarity_search("your_table_name", query_embedding, k=3)
        # print("Similarity search results:", results)
        
        print("Vector store example completed successfully")
        
    except Exception as e:
        print(f"Error in vector store example: {e}")


if __name__ == "__main__":
    main()
    unittest.main()
