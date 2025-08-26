"""
Base extractor interface for OASM Assistant
Abstract base class for all document extractors
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Union
from pathlib import Path


class FileExtractor(ABC):
    """
    Abstract base class for document extractors
    
    All extractors should inherit from this class and implement
    the required methods for consistent interface
    """
    
    @abstractmethod
    def extract_file(self, source: Union[str, Path]) -> str:
        """
        Extract content from a single file
        
        Args:
            source: Path to the file to extract from
            
        Returns:
            Extracted text content
            
        Raises:
            FileNotFoundError: If source file doesn't exist
            Exception: If extraction fails
        """
        pass
        
    @abstractmethod
    def extract_all(self) -> Dict[str, str]:
        """
        Extract content from all supported files in the base directory
        
        Returns:
            Dictionary mapping file paths to extracted content
            Format: {file_path: content}
            
        Raises:
            FileNotFoundError: If base directory doesn't exist
            Exception: If extraction fails
        """
        pass
