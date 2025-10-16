"""
Extract metadata for embeddings
"""
import os
from datetime import datetime
from typing import Dict, Any
from pathlib import Path
from common.logger import logger
import PyPDF2

class MetadataExtractor:

    def __init__(self):
            self.PyPDF2 = PyPDF2

    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Extract metadata from PDF file.

        Args:
        file_path: Path to PDF file

        Returns:
        Dict containing standardized metadata information
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File does not exist: {file_path}")
        
        path = Path(file_path)
        if path.suffix.lower() != '.pdf':
            raise ValueError("Only PDF files are supported")
        
        # Get basic information about a file
        stats = path.stat()
        metadata = {
            'file_name': path.name,
            'file_size': stats.st_size,  # bytes
            'created_at': datetime.fromtimestamp(stats.st_ctime).isoformat(),
            'modified_at': datetime.fromtimestamp(stats.st_mtime).isoformat(),
            'file_extension': path.suffix.lower(),
            'file_type': 'pdf'
        }
        
        # Extract metadata from PDF
        try:
            with open(path, 'rb') as f:
                pdf_reader = self.PyPDF2.PdfReader(f)
                doc_info = pdf_reader.metadata
                
                if doc_info:
                    # Add metadata fields from PDF
                    metadata.update({
                        'title': str(doc_info.get('/Title', '')),
                        'author': str(doc_info.get('/Author', '')),
                        'subject': str(doc_info.get('/Subject', '')),
                        'keywords': str(doc_info.get('/Keywords', '')),
                        'creator': str(doc_info.get('/Creator', '')),
                        'producer': str(doc_info.get('/Producer', '')),
                        'creation_date': str(doc_info.get('/CreationDate', '')),
                        'modification_date': str(doc_info.get('/ModDate', '')),
                        'page_count': len(pdf_reader.pages)
                    })
                    
                    # More information about pages
                    metadata['pages'] = [
                        {
                            'page_number': i + 1,
                            'page_size': str(pdf_reader.pages[i].mediabox)
                        }
                        for i in range(min(50, len(pdf_reader.pages)))  #Limit the number of pages to avoid data overload
                    ]
                    
        except Exception as e:
            logger.warning(f"Cannot read metadata from PDF {file_path}: {str(e)}")
        
        return self._normalize_metadata(metadata)
    
    def _normalize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize metadata to match embeddings.

        Args:
        metadata: Dict containing raw metadata

        Returns:
        Dict containing normalized metadata
        """
        normalized = {}
        
        for key, value in metadata.items():
            # Ignore null values
            if value is None or value == '':
                continue
                
            # Convert all keys to lowercase and replace spaces with underscores
            normalized_key = str(key).lower().replace(' ', '_')
            
            # Convert values ​​to appropriate form
            if isinstance(value, (int, float, bool, str)):
                normalized[normalized_key] = value
            elif hasattr(value, 'isoformat'):
                normalized[normalized_key] = value.isoformat()
            else:
                normalized[normalized_key] = str(value)
        
        return normalized