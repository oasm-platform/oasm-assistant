"""
Advanced filtering for RAG system
"""
from typing import List, Tuple, Dict, Any, Optional, Union
from data.indexing.vector_store import PgVectorStore
from data.embeddings.embeddings import Embeddings
from common.logger import logger
from data.database import postgres_db as db
from sqlalchemy import text
import re
import math
from datetime import datetime, timedelta


class FilterEngine:
    """
    Advanced filtering engine for search results in RAG system.
    Provides various filtering capabilities including metadata, date range,
    quality assessment, and custom filtering rules.
    """
    
    def __init__(
        self,
        vector_store: Optional[PgVectorStore] = None,
        embedding_model: Optional[Any] = None
    ):
        """
        Initialize the filter engine.
        
        Args:
            vector_store: PgVectorStore instance for database operations
            embedding_model: Embedding model for potential semantic filtering
        """
        self.vector_store = vector_store or PgVectorStore()
        self.embedding_model = embedding_model or Embeddings.create_embedding('sentence_transformer')
    
    def filter_by_metadata(
        self,
        results: List[Tuple[float, Dict[str, Any]]],
        filters: Dict[str, Any]
    ) -> List[Tuple[float, Dict[str, Any]]]:
        """
        Filter results by metadata fields.
        
        Args:
            results: List of (score, metadata) tuples from search
            filters: Dictionary of metadata field-value pairs to filter by
            
        Returns:
            Filtered list of (score, metadata) tuples
        """
        filtered_results = []
        
        for score, metadata in results:
            include_result = True
            
            for field, expected_value in filters.items():
                actual_value = metadata.get(field)
                
                if actual_value is None:
                    include_result = False
                    break
                
                # Handle different types of comparisons
                if isinstance(expected_value, dict):
                    # Handle range queries like {"min": 10, "max": 20}
                    if "min" in expected_value and "max" in expected_value:
                        if not (expected_value["min"] <= actual_value <= expected_value["max"]):
                            include_result = False
                            break
                    elif "gt" in expected_value:
                        if not (actual_value > expected_value["gt"]):
                            include_result = False
                            break
                    elif "gte" in expected_value:
                        if not (actual_value >= expected_value["gte"]):
                            include_result = False
                            break
                    elif "lt" in expected_value:
                        if not (actual_value < expected_value["lt"]):
                            include_result = False
                            break
                    elif "lte" in expected_value:
                        if not (actual_value <= expected_value["lte"]):
                            include_result = False
                            break
                elif isinstance(expected_value, list):
                    # Handle "in" queries
                    if actual_value not in expected_value:
                        include_result = False
                        break
                else:
                    # Handle exact match
                    if actual_value != expected_value:
                        include_result = False
                        break
            
            if include_result:
                filtered_results.append((score, metadata))
        
        return filtered_results
    
    def filter_by_date_range(
        self,
        results: List[Tuple[float, Dict[str, Any]]],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        date_field: str = "created_at"
    ) -> List[Tuple[float, Dict[str, Any]]]:
        """
        Filter results by date range.
        
        Args:
            results: List of (score, metadata) tuples from search
            start_date: Start date for filtering (inclusive)
            end_date: End date for filtering (inclusive)
            date_field: Name of the date field in metadata (default: "created_at")
            
        Returns:
            Filtered list of (score, metadata) tuples
        """
        filtered_results = []
        
        for score, metadata in results:
            date_value = metadata.get(date_field)
            
            if date_value is None:
                continue  # Skip if no date value
            
            # Convert string dates to datetime if needed
            if isinstance(date_value, str):
                try:
                    date_value = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
                except ValueError:
                    continue  # Skip if date format is invalid
            
            # Check if date is within range
            include_result = True
            if start_date and date_value < start_date:
                include_result = False
            if end_date and date_value > end_date:
                include_result = False
            
            if include_result:
                filtered_results.append((score, metadata))
        
        return filtered_results
    
    def filter_by_quality(
        self,
        results: List[Tuple[float, Dict[str, Any]]],
        min_score: Optional[float] = None,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        text_field: str = "text"
    ) -> List[Tuple[float, Dict[str, Any]]]:
        """
        Filter results by quality metrics.
        
        Args:
            results: List of (score, metadata) tuples from search
            min_score: Minimum score threshold
            min_length: Minimum text length
            max_length: Maximum text length
            text_field: Name of the text field in metadata (default: "text")
            
        Returns:
            Filtered list of (score, metadata) tuples
        """
        filtered_results = []
        
        for original_score, metadata in results:
            # Check score threshold
            if min_score is not None and original_score < min_score:
                continue
            
            # Check text length if text field exists
            text_content = metadata.get(text_field, "")
            if isinstance(text_content, str):
                text_length = len(text_content)
                
                if min_length is not None and text_length < min_length:
                    continue
                if max_length is not None and text_length > max_length:
                    continue
            
            filtered_results.append((original_score, metadata))
        
        return filtered_results
    
    def filter_by_content(
        self,
        results: List[Tuple[float, Dict[str, Any]]],
        include_keywords: Optional[List[str]] = None,
        exclude_keywords: Optional[List[str]] = None,
        text_field: str = "text",
        case_sensitive: bool = False
    ) -> List[Tuple[float, Dict[str, Any]]]:
        """
        Filter results by content keywords.
        
        Args:
            results: List of (score, metadata) tuples from search
            include_keywords: List of keywords that must be present
            exclude_keywords: List of keywords to exclude
            text_field: Name of the text field in metadata (default: "text")
            case_sensitive: Whether to perform case-sensitive matching
            
        Returns:
            Filtered list of (score, metadata) tuples
        """
        filtered_results = []
        
        for score, metadata in results:
            text_content = metadata.get(text_field, "")
            
            if not isinstance(text_content, str):
                continue
            
            # Prepare text for matching
            search_text = text_content if case_sensitive else text_content.lower()

            # Convert keywords to lowercase if case-insensitive
            search_include = include_keywords
            search_exclude = exclude_keywords
            if not case_sensitive:
                if include_keywords:
                    search_include = [kw.lower() for kw in include_keywords]
                if exclude_keywords:
                    search_exclude = [kw.lower() for kw in exclude_keywords]

            # Check include keywords
            if search_include:
                if not all(keyword in search_text for keyword in search_include):
                    continue

            # Check exclude keywords
            if search_exclude:
                if any(keyword in search_text for keyword in search_exclude):
                    continue
            
            filtered_results.append((score, metadata))
        
        return filtered_results
    
    def filter_by_relevance_score(
        self,
        results: List[Tuple[float, Dict[str, Any]]],
        min_relevance: Optional[float] = None,
        max_relevance: Optional[float] = None
    ) -> List[Tuple[float, Dict[str, Any]]]:
        """
        Filter results by relevance score.
        
        Args:
            results: List of (score, metadata) tuples from search
            min_relevance: Minimum relevance score (0-1)
            max_relevance: Maximum relevance score (0-1)
            
        Returns:
            Filtered list of (score, metadata) tuples
        """
        filtered_results = []
        
        for score, metadata in results:
            include_result = True
            
            if min_relevance is not None and score < min_relevance:
                include_result = False
            if max_relevance is not None and score > max_relevance:
                include_result = False
            
            if include_result:
                filtered_results.append((score, metadata))
        
        return filtered_results
    
    def semantic_filter(
        self,
        results: List[Tuple[float, Dict[str, Any]]],
        reference_text: str,
        threshold: float = 0.5,
        text_field: str = "text"
    ) -> List[Tuple[float, Dict[str, Any]]]:
        """
        Filter results by semantic similarity to a reference text.
        
        Args:
            results: List of (score, metadata) tuples from search
            reference_text: Text to compare against for semantic similarity
            threshold: Minimum similarity threshold (0-1)
            text_field: Name of the text field in metadata (default: "text")
            
        Returns:
            Filtered list of (score, metadata) tuples
        """
        try:
            # Generate embedding for reference text
            reference_embedding = self.embedding_model.embed_query(reference_text)
            
            filtered_results = []
            
            for original_score, metadata in results:
                text_content = metadata.get(text_field, "")
                
                if not isinstance(text_content, str) or not text_content.strip():
                    continue
                
                # Generate embedding for result text
                result_embedding = self.embedding_model.embed_query(text_content)
                
                # Calculate cosine similarity
                similarity = self._cosine_similarity(reference_embedding, result_embedding)
                
                # Only include results above threshold
                if similarity >= threshold:
                    # Optionally adjust the original score based on semantic similarity
                    adjusted_score = (original_score + similarity) / 2
                    filtered_results.append((adjusted_score, metadata))
            
            return filtered_results
            
        except Exception as e:
            logger.error(f"Error in semantic filtering: {e}")
            return results  # Return original results if semantic filtering fails
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity score between 0 and 1
        """
        # Calculate dot product
        dot_product = sum(a * b for a, b in zip(vec1, vec2))

        # Calculate magnitudes
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))

        # Handle zero magnitude
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        # Calculate cosine similarity
        similarity = dot_product / (magnitude1 * magnitude2)

        # Ensure similarity is in [0, 1] range (though should naturally be in [-1, 1])
        return max(0.0, min(1.0, (similarity + 1) / 2))
    
    def apply_multiple_filters(
        self,
        results: List[Tuple[float, Dict[str, Any]]],
        metadata_filters: Optional[Dict[str, Any]] = None,
        date_range: Optional[Tuple[Optional[datetime], Optional[datetime]]] = None,
        quality_filters: Optional[Dict[str, Any]] = None,
        content_filters: Optional[Dict[str, Any]] = None,
        relevance_range: Optional[Tuple[Optional[float], Optional[float]]] = None,
        semantic_reference: Optional[Tuple[str, float]] = None
    ) -> List[Tuple[float, Dict[str, Any]]]:
        """
        Apply multiple filters sequentially to the results.
        
        Args:
            results: List of (score, metadata) tuples from search
            metadata_filters: Dictionary of metadata field-value pairs to filter by
            date_range: Tuple of (start_date, end_date) for date filtering
            quality_filters: Dictionary with min_score, min_length, max_length
            content_filters: Dictionary with include_keywords, exclude_keywords
            relevance_range: Tuple of (min_relevance, max_relevance)
            semantic_reference: Tuple of (reference_text, threshold) for semantic filtering
            
        Returns:
            Filtered list of (score, metadata) tuples after applying all filters
        """
        filtered_results = results
        
        # Apply metadata filters
        if metadata_filters:
            filtered_results = self.filter_by_metadata(filtered_results, metadata_filters)
        
        # Apply date range filters
        if date_range:
            start_date, end_date = date_range
            filtered_results = self.filter_by_date_range(
                filtered_results, start_date, end_date
            )
        
        # Apply quality filters
        if quality_filters:
            min_score = quality_filters.get('min_score')
            min_length = quality_filters.get('min_length')
            max_length = quality_filters.get('max_length')
            text_field = quality_filters.get('text_field', 'text')
            
            filtered_results = self.filter_by_quality(
                filtered_results,
                min_score=min_score,
                min_length=min_length,
                max_length=max_length,
                text_field=text_field
            )
        
        # Apply content filters
        if content_filters:
            include_keywords = content_filters.get('include_keywords')
            exclude_keywords = content_filters.get('exclude_keywords')
            text_field = content_filters.get('text_field', 'text')
            case_sensitive = content_filters.get('case_sensitive', False)
            
            filtered_results = self.filter_by_content(
                filtered_results,
                include_keywords=include_keywords,
                exclude_keywords=exclude_keywords,
                text_field=text_field,
                case_sensitive=case_sensitive
            )
        
        # Apply relevance score filters
        if relevance_range:
            min_relevance, max_relevance = relevance_range
            filtered_results = self.filter_by_relevance_score(
                filtered_results,
                min_relevance=min_relevance,
                max_relevance=max_relevance
            )
        
        # Apply semantic filters
        if semantic_reference:
            reference_text, threshold = semantic_reference
            filtered_results = self.semantic_filter(
                filtered_results,
                reference_text=reference_text,
                threshold=threshold
            )
        
        return filtered_results