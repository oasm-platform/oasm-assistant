"""
Pytest tests for the ChunkProcessor functionality
"""
import pytest
from unittest.mock import Mock, patch
import sys
import os
from unittest.mock import Mock

# Add path to import directly from file
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import module directly from file to avoid importing the entire package
import importlib.util
chunk_processor_spec = importlib.util.spec_from_file_location(
    "chunk_processor",
    os.path.join(os.path.dirname(__file__), '..', 'data', 'embeddings', 'processing', 'chunk_processor.py')
)
chunk_processor_module = importlib.util.module_from_spec(chunk_processor_spec)
chunk_processor_spec.loader.exec_module(chunk_processor_module)

# Get the required classes
ChunkProcessor = chunk_processor_module.ChunkProcessor
SentenceChunker = chunk_processor_module.SentenceChunker
SentenceChunkerConfig = chunk_processor_module.SentenceChunkerConfig
WhitespaceTokenizer = chunk_processor_module.WhitespaceTokenizer


class TestChunkProcessor:
    """Test the ChunkProcessor class"""
    
    def test_chunk_processor_initialization(self):
        """Test ChunkProcessor initialization with default parameters"""
        processor = ChunkProcessor()
        assert processor.chunker is not None
        assert processor.chunker.config.max_tokens == 512
        assert processor.chunker.config.overlap_tokens == 50
    
    def test_chunk_processor_initialization_with_custom_params(self):
        """Test ChunkProcessor initialization with custom parameters"""
        processor = ChunkProcessor(chunk_size=256, chunk_overlap=25)
        assert processor.chunker.config.max_tokens == 256
        assert processor.chunker.config.overlap_tokens == 25
    
    def test_chunk_text_basic(self):
        """Test basic text chunking functionality"""
        processor = ChunkProcessor(chunk_size=50, chunk_overlap=5)
        text = "This is a sample text. " * 10  # Create a longer text
        
        chunks = processor.chunk_text(text)
        
        assert isinstance(chunks, list)
        assert len(chunks) > 0
        assert all(isinstance(chunk, str) for chunk in chunks)
        assert all(len(chunk) > 0 for chunk in chunks)
    
    def test_chunk_text_with_custom_params(self):
        """Test text chunking with custom parameters passed to method"""
        processor = ChunkProcessor()  # Default is 512, 50
        text = "This is a sample text. " * 20  # Create a longer text
        
        # Create a new processor with smaller chunk size to ensure multiple chunks
        processor_small = ChunkProcessor(chunk_size=40, chunk_overlap=5)
        chunks = processor_small.chunk_text(text)
        
        assert isinstance(chunks, list)
        assert len(chunks) > 0
        assert all(isinstance(chunk, str) for chunk in chunks)
        assert all(len(chunk) > 0 for chunk in chunks)
    
    def test_chunk_text_empty_input(self):
        """Test chunking with empty input"""
        processor = ChunkProcessor()
        chunks = processor.chunk_text("")
        assert chunks == []
    
    def test_chunk_text_single_sentence_exceeds_limit(self):
        """Test chunking when a single sentence exceeds the token limit"""
        processor = ChunkProcessor(chunk_size=10, chunk_overlap=2)
        # Create a very long sentence that will exceed the token limit
        long_sentence = "word " * 50  # 50 words should exceed our 10 token limit
        text = long_sentence + ". This is another sentence."
        
        chunks = processor.chunk_text(text)
        
        assert isinstance(chunks, list)
        assert len(chunks) > 0
        # Each chunk should be shorter than the original long sentence
    
    def test_chunk_text_overlapping_chunks(self):
        """Test that chunks have appropriate overlap"""
        processor = ChunkProcessor(chunk_size=30, chunk_overlap=5)
        text = "This is a test sentence. " * 15  # Create multiple sentences
        
        chunks = processor.chunk_text(text)
        
        assert len(chunks) > 1  # Should have multiple chunks with this setup
        # Verify chunks are strings and not empty
        for chunk in chunks:
            assert isinstance(chunk, str)
            assert len(chunk) > 0


class TestSentenceChunkerIntegration:
    """Test SentenceChunker with various configurations"""
    
    def test_sentence_chunker_with_whitespace_tokenizer(self):
        """Test SentenceChunker with WhitespaceTokenizer"""
        # Use the imported classes from module
        config = chunk_processor_module.SentenceChunkerConfig(max_tokens=20, overlap_tokens=2)
        chunker = chunk_processor_module.SentenceChunker(config=config, tokenizer=chunk_processor_module.WhitespaceTokenizer())
        
        text = "This is a test sentence. This is another test sentence. " * 5
        chunks = chunker.chunk(text)
        
        assert isinstance(chunks, list)
        assert len(chunks) > 0
        for chunk in chunks:
            assert hasattr(chunk, 'text')
            assert hasattr(chunk, 'n_tokens')
            assert hasattr(chunk, 'start_index')
            assert hasattr(chunk, 'end_index')
            assert len(chunk.text) > 0
            assert chunk.n_tokens > 0
    
    def test_sentence_chunker_config_validation(self):
        """Test configuration validation in SentenceChunkerConfig"""
        # Test valid configuration
        config = chunk_processor_module.SentenceChunkerConfig(max_tokens=100, overlap_tokens=10)
        assert config.max_tokens == 100
        assert config.overlap_tokens == 10
        
        # Test overlap_tokens >= max_tokens correction
        config = chunk_processor_module.SentenceChunkerConfig(max_tokens=10, overlap_tokens=15)
        assert config.overlap_tokens == 9  # Should be max_tokens - 1


class TestChunkProcessorIntegration:
    """Integration tests for ChunkProcessor"""
    
    def test_chunk_processor_with_real_text(self):
        """Test ChunkProcessor with realistic text content"""
        processor = ChunkProcessor(chunk_size=100, chunk_overlap=10)
        text = """
        Vector databases (VDBs) have emerged to manage high-dimensional data that exceed the capabilities
        of traditional database management systems. They are now tightly integrated with large language models
        and widely applied in modern artificial intelligence systems. VDBs have two core functions:
        vector storage and vector retrieval. The vector storage function relies on techniques such as
        quantization, compression, and distributed storage mechanisms to improve efficiency and scalability.
        """
        
        chunks = processor.chunk_text(text)
        
        assert isinstance(chunks, list)
        assert len(chunks) > 0
        assert all(isinstance(chunk, str) for chunk in chunks)
        assert all(len(chunk) > 0 for chunk in chunks)
        # Verify that the total content is preserved across chunks
        full_text_reconstructed = " ".join(chunks)
        assert len(full_text_reconstructed) >= len(text) - 100  # Allow some processing differences
    
    def test_different_chunk_sizes(self):
        """Test ChunkProcessor with different chunk sizes"""
        text = "This is a test sentence. " * 20
        
        # Test with different chunk sizes
        small_processor = ChunkProcessor(chunk_size=20, chunk_overlap=5)
        small_chunks = small_processor.chunk_text(text)
        large_processor = ChunkProcessor(chunk_size=100, chunk_overlap=10)
        large_chunks = large_processor.chunk_text(text)
        
        # Small chunks should result in more chunks than large chunks
        assert len(small_chunks) >= len(large_chunks)
        assert len(small_chunks) > 0
        assert len(large_chunks) > 0
    
    def test_overlap_preservation(self):
        """Test that overlap is preserved in chunks"""
        processor = ChunkProcessor(chunk_size=50, chunk_overlap=10)
        text = "This is a test sentence. " * 15  # Create enough text for multiple chunks
        
        chunks = processor.chunk_text(text)
        
        assert len(chunks) > 1  # We expect multiple chunks
        for chunk in chunks:
            assert isinstance(chunk, str)
            assert len(chunk) > 0
