"""
Batch embedding processing
"""
"""
Batch processing pipeline for text embedding with quality assessment.
Processes text through: metadata extraction -> text preprocessing -> chunking -> embedding -> quality assessment.

This version uses a simple TF-IDF based embedding approach to avoid external dependencies.
"""

import numpy as np
from typing import Dict, List, Tuple, Any, Optional
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import math

# Import required modules
from .text_preprocessor import TextPreprocessor
from .chunk_processor import SentenceChunker
from .quality_assessor import EmbeddingQualityAssessor
from .metadata_extractor import MetadataExtractor

class SimpleEmbedding:
    """A simple TF-IDF based embedding model for demonstration purposes."""
    
    def __init__(self, dimension: int = 100):
        self.dimension = dimension
        self.vocab = {}
        self.idf = {}
        self.vocab_size = 0
        self.doc_count = 0
        
    def fit(self, documents: List[str]):
        """Fit the model on a list of documents."""
        # Simple word frequency counting
        doc_freq = defaultdict(int)
        
        for doc in documents:
            words = doc.lower().split()
            for word in set(words):  # Count document frequency
                doc_freq[word] += 1
                
        # Build vocabulary
        self.vocab = {word: idx for idx, word in enumerate(sorted(doc_freq.keys()))}
        self.vocab_size = len(self.vocab)
        self.doc_count = len(documents)
        
        # Calculate IDF (Inverse Document Frequency)
        for word, count in doc_freq.items():
            self.idf[word] = math.log((self.doc_count + 1) / (count + 1)) + 1
            
    def embed(self, text: str) -> List[float]:
        """Create an embedding for a single text."""
        if not self.vocab:
            # If not fitted, return random embedding
            return list(np.random.randn(self.dimension))
            
        # Simple TF-IDF embedding
        word_counts = defaultdict(int)
        words = text.lower().split()
        for word in words:
            word_counts[word] += 1
            
        # Create sparse TF-IDF vector
        embedding = [0.0] * self.dimension
        for word, count in word_counts.items():
            if word in self.vocab:
                idx = self.vocab[word] % self.dimension
                tf = count / len(words)
                idf = self.idf.get(word, 1.0)
                embedding[idx] += tf * idf
                
        # Normalize
        norm = math.sqrt(sum(x*x for x in embedding)) or 1.0
        return [x / norm for x in embedding]

class TextProcessingPipeline:
    """
    End-to-end text processing pipeline for generating and evaluating embeddings.
    """
    
    def __init__(self, embedding_dim: int = 100):
        """
        Initialize the pipeline with default components.
        
        Args:
            embedding_dim: Dimension of the embedding vectors (default: 100)
        """
        self.text_preprocessor = TextPreprocessor()
        self.chunker = SentenceChunker()
        self.embedding_model = SimpleEmbedding(dimension=embedding_dim)
        self.quality_assessor = EmbeddingQualityAssessor()
        self.metadata_extractor = MetadataExtractor()
        self.is_fitted = False
    
    def process_text(self, text: str, source_info: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Process text through the entire pipeline.
        
        Args:
            text: Input text to process
            source_info: Optional dictionary with source file information
            
        Returns:
            Dictionary containing processed chunks, embeddings, and quality metrics
        """
        # 1. Generate metadata
        metadata = self._generate_metadata(text, source_info)
        
        # 2. Preprocess text
        preprocessed_text = self.text_preprocessor.preprocess(text)
        
        # 3. Chunk text
        chunks = [chunk.text for chunk in self.chunker.chunk(preprocessed_text)]
        
        # 4. Fit the embedding model if not already fitted
        if not self.is_fitted and chunks:
            self.embedding_model.fit(chunks)
            self.is_fitted = True
        
        # 5. Generate embeddings
        embeddings = [self.embedding_model.embed(chunk) for chunk in chunks]
        
        # 6. Assess quality if we have multiple chunks
        quality_metrics = {}
        if len(embeddings) > 1:
            quality_metrics = self._assess_quality(embeddings)
        
        return {
            "metadata": metadata,
            "chunks": chunks,
            "embeddings": embeddings,
            "quality_metrics": quality_metrics
        }
    
    def _generate_metadata(self, text: str, source_info: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate metadata for the input text."""
        metadata = {
            "processing_timestamp": datetime.utcnow().isoformat(),
            "text_length": len(text),
            "word_count": len(text.split()),
            "source": source_info or {}
        }
        return metadata
    
    def _assess_quality(self, embeddings: List[List[float]]) -> Dict[str, float]:
        """Assess the quality of generated embeddings."""
        if not embeddings:
            return {}
            
        np_embeddings = np.array(embeddings)
        return {
            "cosine_similarity": self.quality_assessor.compute_cosine_similarity(np_embeddings),
            "embedding_variance": self.quality_assessor.compute_embedding_variance(np_embeddings),
            "avg_nearest_neighbor_dist": self.quality_assessor.compute_nearest_neighbor_distance(np_embeddings)
        }
