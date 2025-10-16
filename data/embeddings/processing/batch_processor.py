"""
Batch Embedding Processing Module

This module provides a pipeline for processing text documents through multiple stages:
1. Metadata extraction 
2. Text preprocessing
3. Text chunking
4. Embedding generation
5. Quality assessment

The pipeline uses a simple TF-IDF based embedding approach for demonstration.
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime
import numpy as np
import math
from collections import defaultdict

from .text_preprocessor import TextPreprocessor
from .chunk_processor import SentenceChunker, Chunk, SentenceChunkerConfig
from .quality_assessor import EmbeddingQualityAssessor
from .metadata_extractor import MetadataExtractor

@dataclass
class ProcessingResult:
    """Container for processing pipeline results"""
    metadata: Dict[str, Any]
    chunks: List[str]
    embeddings: List[List[float]]
    quality_metrics: Dict[str, float]

class TFIDFEmbedding:
    """TF-IDF based embedding model"""
    
    def __init__(self, dimension: int = 100):
        self.dimension = dimension
        self.vocab: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.vocab_size = 0
        self.doc_count = 0
        # Add cache buffer to improve performance
        self._word_cache: Dict[str, List[float]] = {}
        # Add coefficient to increase vector distinction
        self.use_sublinear_tf = True  # Use log(tf) instead of linear tf
        self.use_inverse_doc_freq = True  # Use IDF to reduce weight of common words
        self.use_l2_normalization = True  # Use L2 normalization to improve vector quality
        
    def fit(self, documents: List[Any]) -> None:
        """
        Fit model on document corpus

        Args:
            documents: List of text documents or Chunk objects
        """
        texts = [doc.text if isinstance(doc, Chunk) else doc for doc in documents]
        
        doc_freq = self._count_document_frequencies(texts)
        self._build_vocabulary(doc_freq)
        self._calculate_idf(doc_freq)

    def _count_document_frequencies(self, documents: List[str]) -> Dict[str, int]:
        """Count word frequencies across documents"""
        doc_freq = defaultdict(int)
        for doc in documents:
            words = set(doc.lower().split())  # Using set for unique words
            for word in words:
                doc_freq[word] += 1
        return doc_freq

    def _build_vocabulary(self, doc_freq: Dict[str, int]) -> None:
        """Build vocabulary from document frequencies"""
        self.vocab = {word: idx for idx, word in enumerate(sorted(doc_freq.keys()))}
        self.vocab_size = len(self.vocab)
        self.doc_count = len(doc_freq)

    def _calculate_idf(self, doc_freq: Dict[str, int]) -> None:
        """Calculate IDF scores"""
        self.idf = {
            word: math.log((self.doc_count + 1) / (count + 1)) + 1
            for word, count in doc_freq.items()
        }

    def embed(self, text: str) -> List[float]:
        """
        Generate embedding for a text
        
        Args:
            text: Input text
            
        Returns:
            Normalized embedding vector
        """
        if not self.vocab:
            return list(np.random.randn(self.dimension))

        # Calculate TF scores
        words = text.lower().split()
        if not words:
            return [0.0] * self.dimension
            
        word_counts = self._count_term_frequencies(words)
        
        # Generate TF-IDF vector
        embedding = self._create_tfidf_vector(word_counts, len(words))
        
        # Normalize
        return self._normalize_vector(embedding)

    def _count_term_frequencies(self, words: List[str]) -> Dict[str, int]:
        """Count word frequencies in text"""
        frequencies = defaultdict(int)
        for word in words:
            frequencies[word] += 1
        return frequencies

    def _create_tfidf_vector(self, word_counts: Dict[str, int], total_words: int) -> List[float]:
        """Create TF-IDF vector from word counts"""
        vector = [0.0] * self.dimension
        for word, count in word_counts.items():
            if word in self.vocab:
                idx = self.vocab[word] % self.dimension
                # Use logarithmic TF instead of linear TF to reduce impact of frequently occurring words
                if self.use_sublinear_tf:
                    tf = 1 + math.log(count) if count > 0 else 0
                else:
                    tf = count / max(1, total_words)

                # Apply IDF if enabled
                if self.use_inverse_doc_freq:
                    idf = self.idf.get(word, 1.0)
                else:
                    idf = 1.0

                # Apply coefficient to increase vector distinction
                # Increase weight for distinctive words
                weight = tf * idf
                vector[idx] += weight

        # Improve distinction by applying a slight adjustment coefficient
        # to increase differences between embedding vectors without losing stability
        for i in range(len(vector)):
            if vector[i] != 0:
                # Apply slight adjustment coefficient to amplify differences
                # while maintaining model stability
                vector[i] = vector[i] * (1.0 + 0.05 * abs(vector[i]))  # Slight amplification proportional to absolute value
        
        return vector

    def _normalize_vector(self, vector: List[float]) -> List[float]:
        """L2 normalize vector"""
        if self.use_l2_normalization:
            norm = math.sqrt(sum(x*x for x in vector)) or 1.0
            return [x / norm for x in vector]
        else:
            return vector

class BatchProcessor:
    """Text processing pipeline with batch support"""
    
    def __init__(self, embedding_dim: int = 100):
        self.embedding_dim = embedding_dim
        self.embedding_model = TFIDFEmbedding(dimension=embedding_dim)
        self.text_preprocessor = TextPreprocessor()
        # Use optimal configuration for performance
        self.chunker = SentenceChunker(config=SentenceChunkerConfig(max_tokens=512, overlap_tokens=64))
        self.quality_assessor = EmbeddingQualityAssessor()
        self.is_fitted = False

    def process_batch(
        self, 
        texts: List[str],
        batch_size: int = 32,
        source_info: Optional[Dict[str, Any]] = None
    ) -> List[ProcessingResult]:
        """
        Process multiple texts in batches
        
        Args:
            texts: List of input texts
            batch_size: Number of texts to process at once
            source_info: Optional metadata about text sources
            
        Returns:
            List of processing results
        """
        results = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_results = [self.process_single(text, source_info) for text in batch]
            results.extend(batch_results)
        return results

    def process_single(
        self, 
        text: str,
        source_info: Optional[Dict[str, Any]] = None
    ) -> ProcessingResult:
        """Process single text through pipeline"""
        
        # Extract metadata
        metadata = self._generate_metadata(text, source_info)
        
        # Preprocess text
        clean_text = self.text_preprocessor.preprocess(text)
        
        # Chunk text
        chunks = self.chunker.chunk(clean_text)
        if not chunks:
            chunks = [clean_text]  # Fallback to the entire text if no chunks are created
        
        # Fit embedding model if needed
        if not self.is_fitted and chunks:
            self.embedding_model.fit([chunk.text for chunk in chunks])  # Pass `chunk.text`
            self.is_fitted = True

        # Generate embeddings for each chunk
        embeddings = [self.embedding_model.embed(chunk.text) for chunk in chunks]  # Pass `chunk.text`
        
        # Convert embeddings to numpy array for quality assessment
        embeddings_array = np.array(embeddings)
        
        # Assess quality
        quality_metrics = self.quality_assessor.assess(embeddings_array) if len(embeddings) > 1 else {}
        
        return ProcessingResult(
            metadata=metadata,
            chunks=chunks,
            embeddings=embeddings,
            quality_metrics=quality_metrics
        )

    def _generate_metadata(
        self,
        text: str,
        source_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate metadata for text"""
        return {
            "processing_timestamp": datetime.utcnow().isoformat(),
            "text_length": len(text),
            "word_count": len(text.split()),
            "source": source_info or {}
        }

    def _assess_quality(self, embeddings: List[List[float]]) -> Dict[str, float]:
        """Assess embedding quality metrics"""
        if not embeddings:
            return {}
            
        embedding_array = np.array(embeddings)
        return {
            "cosine_similarity": self.quality_assessor.compute_cosine_similarity(embedding_array),
            "embedding_variance": self.quality_assessor.compute_embedding_variance(embedding_array),
            "avg_nearest_neighbor_dist": self.quality_assessor.compute_nearest_neighbor_distance(embedding_array)
        }
