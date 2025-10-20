"""
Tests for embedding interface consistency and functionality
"""
import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.embeddings import get_embedding_model, Embeddings
from data.embeddings.models import (
    BaseEmbedding,
    SentenceTransformerEmbedding,
)
from common.config import EmbeddingConfigs
from common.logger import logger


class TestEmbeddingInterface:
    """Test embedding interface consistency"""

    def test_base_embedding_interface(self):
        """Test that BaseEmbedding has correct interface"""
        # Create a config
        config = EmbeddingConfigs(
            _env_file=None,
            EMBEDDING_MODEL_NAME="test-model"
        )

        # BaseEmbedding is abstract, but we can check its signature
        import inspect
        sig = inspect.signature(BaseEmbedding.__init__)
        params = list(sig.parameters.keys())

        # Should have self and embedding_settings
        assert 'embedding_settings' in params, "BaseEmbedding should accept embedding_settings"
        logger.info("✓ BaseEmbedding interface is correct")

    def test_sentence_transformer_initialization(self):
        """Test SentenceTransformerEmbedding initialization"""
        config = EmbeddingConfigs(
            _env_file=None,
            EMBEDDING_MODEL_NAME="all-MiniLM-L6-v2"
        )

        model = SentenceTransformerEmbedding(config)

        # Check attributes
        assert hasattr(model, 'embedding_settings')
        assert hasattr(model, 'name')
        assert hasattr(model, 'embedding_model')
        assert model.name == "all-MiniLM-L6-v2"

        logger.info(f"✓ SentenceTransformer initialized: {model.name}")

    def test_embedding_has_required_methods(self):
        """Test that embedding has required methods"""
        config = EmbeddingConfigs(
            _env_file=None,
            EMBEDDING_MODEL_NAME="all-MiniLM-L6-v2"
        )

        model = SentenceTransformerEmbedding(config)

        # Check methods exist
        assert hasattr(model, 'encode'), "Model should have encode method"
        assert hasattr(model, 'dim'), "Model should have dim property"
        assert callable(model.encode), "encode should be callable"

        logger.info("✓ Required methods present")

    def test_embedding_encode_single_string(self):
        """Test encoding a single string"""
        config = EmbeddingConfigs(
            _env_file=None,
            EMBEDDING_MODEL_NAME="all-MiniLM-L6-v2"
        )

        model = SentenceTransformerEmbedding(config)

        # Encode single string
        text = "Hello world"
        embedding = model.encode(text)

        # Check result
        assert isinstance(embedding, list), "Should return list"
        assert len(embedding) > 0, "Embedding should not be empty"
        assert all(isinstance(x, float) for x in embedding), "All elements should be float"

        logger.info(f"✓ Single string encoded: {len(embedding)} dimensions")

    def test_embedding_encode_multiple_strings(self):
        """Test encoding multiple strings"""
        config = EmbeddingConfigs(
            _env_file=None,
            EMBEDDING_MODEL_NAME="all-MiniLM-L6-v2"
        )

        model = SentenceTransformerEmbedding(config)

        # Encode multiple strings
        texts = ["Hello world", "Python programming", "Machine learning"]
        embeddings = model.encode(texts)

        # Check result
        assert isinstance(embeddings, list), "Should return list"
        assert len(embeddings) == 3, "Should have 3 embeddings"
        assert all(isinstance(emb, list) for emb in embeddings), "Each should be a list"
        assert all(len(emb) > 0 for emb in embeddings), "Each embedding should not be empty"

        logger.info(f"✓ Multiple strings encoded: {len(embeddings)} embeddings")

    def test_embedding_dim_property(self):
        """Test dim property returns correct dimension"""
        config = EmbeddingConfigs(
            _env_file=None,
            EMBEDDING_MODEL_NAME="all-MiniLM-L6-v2"
        )

        model = SentenceTransformerEmbedding(config)

        # Get dimension
        dim = model.dim

        # Check dimension
        assert isinstance(dim, int), "Dimension should be integer"
        assert dim > 0, "Dimension should be positive"
        assert dim == 384, "all-MiniLM-L6-v2 should have 384 dimensions"

        logger.info(f"✓ Dimension property works: {dim}")

    def test_embedding_consistency(self):
        """Test that same text produces same embedding"""
        config = EmbeddingConfigs(
            _env_file=None,
            EMBEDDING_MODEL_NAME="all-MiniLM-L6-v2"
        )

        model = SentenceTransformerEmbedding(config)

        text = "Test consistency"
        embedding1 = model.encode(text)
        embedding2 = model.encode(text)

        # Should be identical
        assert embedding1 == embedding2, "Same text should produce same embedding"

        logger.info("✓ Embedding consistency verified")

    def test_factory_create_embedding(self):
        """Test factory pattern for creating embeddings"""
        # Use factory to create embedding
        model = Embeddings.create_embedding(
            'sentence_transformer',
            model_name='all-MiniLM-L6-v2'
        )

        # Check type
        assert isinstance(model, BaseEmbedding), "Should return BaseEmbedding instance"
        assert isinstance(model, SentenceTransformerEmbedding), "Should be SentenceTransformer"
        assert model.name == 'all-MiniLM-L6-v2'

        logger.info(f"✓ Factory created: {type(model).__name__}")

    def test_get_embedding_model_helper(self):
        """Test get_embedding_model helper function"""
        model = get_embedding_model()

        # Check type
        assert isinstance(model, BaseEmbedding), "Should return BaseEmbedding instance"
        assert hasattr(model, 'encode'), "Should have encode method"
        assert hasattr(model, 'dim'), "Should have dim property"

        logger.info(f"✓ Helper function works: {type(model).__name__}")


class TestEmbeddingIntegration:
    """Integration tests for embedding workflow"""

    def test_full_embedding_workflow(self):
        """Test complete workflow from creation to encoding"""
        logger.info("\n" + "=" * 60)
        logger.info("INTEGRATION TEST: Full Embedding Workflow")
        logger.info("=" * 60)

        # Step 1: Create embedding model
        model = get_embedding_model()
        logger.info("✓ Step 1: Model created")

        # Step 2: Check attributes
        assert model.name is not None
        assert model.embedding_settings is not None
        logger.info(f"✓ Step 2: Model name = {model.name}")

        # Step 3: Get dimension
        dim = model.dim
        logger.info(f"✓ Step 3: Dimension = {dim}")

        # Step 4: Encode single text
        text = "Security vulnerability detection"
        embedding = model.encode(text)
        assert len(embedding) == dim
        logger.info(f"✓ Step 4: Single text encoded ({len(embedding)} dims)")

        # Step 5: Encode multiple texts
        texts = [
            "SQL injection attack",
            "Cross-site scripting",
            "Remote code execution"
        ]
        embeddings = model.encode(texts)
        assert len(embeddings) == len(texts)
        assert all(len(emb) == dim for emb in embeddings)
        logger.info(f"✓ Step 5: Multiple texts encoded ({len(embeddings)} embeddings)")

        logger.info("\n" + "=" * 60)
        logger.info("INTEGRATION TEST PASSED!")
        logger.info("=" * 60 + "\n")


def test_embedding_interface_summary():
    """Summary test showing all capabilities"""
    logger.info("\n" + "=" * 70)
    logger.info("EMBEDDING INTERFACE TEST SUMMARY")
    logger.info("=" * 70)

    # Create model
    model = get_embedding_model()
    logger.info(f"\n1. Model Type: {type(model).__name__}")
    logger.info(f"2. Model Name: {model.name}")
    logger.info(f"3. Embedding Dimension: {model.dim}")

    # Test encoding
    test_text = "Nuclei security template"
    embedding = model.encode(test_text)
    logger.info(f"4. Test Encoding: '{test_text}' -> {len(embedding)} dimensions")

    # Test batch encoding
    batch_texts = ["Test 1", "Test 2", "Test 3"]
    batch_embeddings = model.encode(batch_texts)
    logger.info(f"5. Batch Encoding: {len(batch_texts)} texts -> {len(batch_embeddings)} embeddings")

    # Verify all embeddings have same dimension
    assert len(embedding) == model.dim
    assert all(len(emb) == model.dim for emb in batch_embeddings)

    logger.info("\n" + "=" * 70)
    logger.info("ALL CAPABILITIES VERIFIED!")
    logger.info("=" * 70 + "\n")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
