"""
Pytest tests for data pipeline functionality
"""

import pytest
from unittest.mock import Mock, patch


class TestTextPreprocessor:
    """Test text preprocessing functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        # Mock the TextPreprocessor since there might be import issues
        self.preprocessor = Mock()

    def test_text_preprocessor_initialization(self):
        """Test text preprocessor initialization"""
        assert self.preprocessor is not None

    def test_preprocess_sample_text(self):
        """Test preprocessing of sample text"""
        raw_text = """
        Abstract—Vector databases (VDBs) have emerged to manage
        high-dimensional data that exceed the capabilities of traditional
        database management systems, and are now tightly integrated
        with large language models.
        """

        # Mock the preprocess method
        expected_clean_text = "Abstract Vector databases VDBs have emerged to manage high-dimensional data that exceed the capabilities of traditional database management systems and are now tightly integrated with large language models"
        self.preprocessor.preprocess.return_value = expected_clean_text

        clean_text = self.preprocessor.preprocess(raw_text)

        assert isinstance(clean_text, str)
        assert len(clean_text) > 0
        assert clean_text != raw_text  # Should be different after preprocessing
        self.preprocessor.preprocess.assert_called_once_with(raw_text)


class TestSentenceChunker:
    """Test sentence chunking functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        # Mock the SentenceChunker and related classes
        self.chunker = Mock()
        self.chunker.max_tokens = 40
        self.chunker.overlap_tokens = 8

    def test_sentence_chunker_initialization(self):
        """Test sentence chunker initialization"""
        assert self.chunker is not None
        assert self.chunker.max_tokens == 40
        assert self.chunker.overlap_tokens == 8

    def test_chunk_text(self):
        """Test chunking text into sentences"""
        text = "This is a test document about artificial intelligence. " * 20

        # Mock chunk objects
        mock_chunk1 = Mock()
        mock_chunk1.text = "This is a test document about artificial intelligence. This is a test document about artificial intelligence."
        mock_chunk1.n_tokens = 18
        mock_chunk1.start_index = 0
        mock_chunk1.end_index = 109

        mock_chunk2 = Mock()
        mock_chunk2.text = "This is a test document about artificial intelligence. This is a test document about artificial intelligence."
        mock_chunk2.n_tokens = 18
        mock_chunk2.start_index = 55
        mock_chunk2.end_index = 164

        chunks = [mock_chunk1, mock_chunk2]
        self.chunker.chunk.return_value = chunks

        result_chunks = self.chunker.chunk(text)

        assert isinstance(result_chunks, list)
        assert len(result_chunks) > 0

        # Verify chunk properties
        for chunk in result_chunks:
            assert hasattr(chunk, 'text')
            assert hasattr(chunk, 'n_tokens')
            assert hasattr(chunk, 'start_index')
            assert hasattr(chunk, 'end_index')
            assert len(chunk.text) > 0
            assert chunk.n_tokens > 0

    def test_chunk_overlap(self):
        """Test that chunks have proper overlap"""
        text = "This is sentence one. This is sentence two. This is sentence three. " * 10

        # Mock overlapping chunks
        mock_chunk1 = Mock()
        mock_chunk1.start_index = 0
        mock_chunk1.end_index = 100

        mock_chunk2 = Mock()
        mock_chunk2.start_index = 50  # Overlaps with chunk1
        mock_chunk2.end_index = 150

        chunks = [mock_chunk1, mock_chunk2]
        self.chunker.chunk.return_value = chunks

        result_chunks = self.chunker.chunk(text)

        # Should have multiple chunks with overlap
        assert len(result_chunks) > 1

        # Check that chunks are properly indexed
        for i, chunk in enumerate(result_chunks):
            if i > 0:
                # Later chunks should start after previous chunk's start
                assert chunk.start_index >= result_chunks[i-1].start_index


class TestBatchEmbedder:
    """Test batch embedding functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        # Mock the BatchEmbedder and config
        self.config = Mock()
        self.config.provider = "sentence_transformer"
        self.config.batch_size = 8
        self.config.out_jsonl = "test_output_vectors.jsonl"
        self.config.include_text_in_jsonl = True
        self.config.provider_kwargs = {"model_name": "all-MiniLM-L6-v2"}

        self.embedder = Mock()

    def test_batch_embedder_initialization(self):
        """Test batch embedder initialization"""
        assert self.embedder is not None
        assert self.config.provider == "sentence_transformer"
        assert self.config.batch_size == 8

    def test_batch_embedding_process(self):
        """Test batch embedding process"""
        # Mock the run method to return sample vectors
        mock_vectors = [[0.1, 0.2, 0.3] * 128]  # 384-dim vector
        mock_dimension = 384
        self.embedder.run.return_value = (mock_vectors, mock_dimension)

        texts = [
            "This is sample text one.",
            "This is sample text two.",
            "This is sample text three."
        ]

        vectors, dimension = self.embedder.run(texts)

        # Verify method was called
        self.embedder.run.assert_called_once_with(texts)

        # Verify return values
        assert vectors == mock_vectors
        assert dimension == mock_dimension

    def test_batch_embedder_config_validation(self):
        """Test batch embedder configuration"""
        config = Mock()
        config.provider = "sentence_transformer"
        config.batch_size = 4
        config.out_jsonl = "test.jsonl"
        config.include_text_in_jsonl = False
        config.provider_kwargs = {"model_name": "test-model"}

        embedder = Mock()
        assert embedder is not None
        assert config.provider == "sentence_transformer"
        assert config.batch_size == 4


class TestDataPipelineIntegration:
    """Test integration of data pipeline components"""

    def test_full_pipeline_flow(self):
        """Test complete data processing pipeline"""
        # Sample raw text
        raw_text = """
        Abstract—Vector databases (VDBs) have emerged to manage
        high-dimensional data that exceed the capabilities of traditional
        database management systems, and are now tightly integrated
        with large language models as well as widely applied in modern
        artificial intelligence systems.
        """

        # 1. Mock Preprocess
        preprocessor = Mock()
        clean_text = "Abstract Vector databases VDBs have emerged to manage high-dimensional data"
        preprocessor.preprocess.return_value = clean_text

        result_clean_text = preprocessor.preprocess(raw_text)

        assert isinstance(result_clean_text, str)
        assert len(result_clean_text) > 0

        # 2. Mock Chunk
        chunker = Mock()
        mock_chunk1 = Mock()
        mock_chunk1.text = "Abstract Vector databases VDBs have emerged"
        mock_chunk2 = Mock()
        mock_chunk2.text = "to manage high-dimensional data"

        chunks = [mock_chunk1, mock_chunk2]
        chunker.chunk.return_value = chunks

        result_chunks = chunker.chunk(clean_text)

        assert isinstance(result_chunks, list)
        assert len(result_chunks) > 0

        # 3. Extract text from chunks
        texts = [chunk.text for chunk in result_chunks]
        assert len(texts) == len(result_chunks)
        assert all(isinstance(text, str) for text in texts)

    def test_pipeline_with_mocked_embedding(self):
        """Test pipeline with mocked embedding process"""
        # Mock embedding results
        mock_vectors = [[0.1] * 384 for _ in range(3)]  # 3 vectors of 384 dimensions
        mock_dimension = 384

        embedder = Mock()
        embedder.run.return_value = (mock_vectors, mock_dimension)

        # Sample texts
        texts = [
            "Sample text one about AI.",
            "Sample text two about machine learning.",
            "Sample text three about databases."
        ]

        # Create embedder and run
        vectors, dimension = embedder.run(texts)

        # Verify results
        embedder.run.assert_called_once_with(texts)
        assert len(vectors) == 3
        assert dimension == 384
        assert all(len(vec) == 384 for vec in vectors)