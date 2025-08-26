import logging
from pathlib import Path
from typing import Dict
from pypdf import PdfReader
from .base_extractor import FileExtractor


class PDFExtractor(FileExtractor):
    def __init__(self, base_folder: str = "knowledge/documents/pdfs"):
        """
        PDFExtractor: Extract text from PDF files or entire PDF folder
        
        Args:
            base_folder: Directory containing PDF files
        """
        self.base_folder = Path(base_folder)
        self.logger = logging.getLogger(__name__)
        
        # Configuration
        self.max_file_size_mb = 100  # Maximum PDF file size in MB
        self.supported_extensions = ['.pdf']

    def extract_file(self, file_path: str) -> str:
        """
        Extract text from a single PDF file
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Extracted text content as string
            
        Raises:
            FileNotFoundError: If PDF file doesn't exist
            ValueError: If file is not a PDF
            Exception: If extraction fails
        """
        file_path = Path(file_path)
        
        # ERROR HANDLING IMPROVEMENT 1: Check file exists
        if not file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")
            
        # ERROR HANDLING IMPROVEMENT 2: Validate file extension
        if file_path.suffix.lower() not in self.supported_extensions:
            raise ValueError(f"File is not a PDF: {file_path}")
            
        # ERROR HANDLING IMPROVEMENT 3: Check file size
        file_size = file_path.stat().st_size
        max_size_bytes = self.max_file_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            raise ValueError(f"PDF file too large: {file_size / 1024 / 1024:.1f}MB > {self.max_file_size_mb}MB")
        
        try:
            self.logger.info(f"Extracting text from PDF: {file_path}")
            
            # Read PDF and extract text
            reader = PdfReader(str(file_path))
            text_parts = []
            
            for page_num, page in enumerate(reader.pages, 1):
                try:
                    text = page.extract_text()
                    if text and text.strip():  # Only add non-empty text
                        text_parts.append(text.strip())
                except Exception as e:
                    self.logger.warning(f"Failed to extract text from page {page_num} of {file_path}: {e}")
                    continue
            
            if not text_parts:
                self.logger.warning(f"No text extracted from PDF: {file_path}")
                return ""
                
            # Join all pages with double newline
            full_text = "\n\n".join(text_parts)
            
            self.logger.info(f"Successfully extracted {len(full_text)} characters from {file_path}")
            return full_text
            
        except Exception as e:
            self.logger.error(f"Failed to extract PDF {file_path}: {e}")
            raise Exception(f"PDF extraction failed: {e}")

    def extract_all(self) -> Dict[str, str]:
        """
        Extract text from all PDF files in the base folder and its subfolders
        
        Returns:
            Dictionary mapping relative file paths to extracted text
            Format: {relative_path: text_content}
            
        Raises:
            FileNotFoundError: If base folder doesn't exist
        """
        results: Dict[str, str] = {}
        
        # ERROR HANDLING IMPROVEMENT 4: Check folder exists
        if not self.base_folder.exists():
            raise FileNotFoundError(f"Folder {self.base_folder} does not exist")
            
        # ERROR HANDLING IMPROVEMENT 5: Check is directory
        if not self.base_folder.is_dir():
            raise ValueError(f"Path {self.base_folder} is not a directory")
        
        self.logger.info(f"Starting PDF extraction from folder: {self.base_folder}")
        
        # RECURSIVE IMPROVEMENT: Use rglob instead of glob to search subfolders
        pdf_files = list(self.base_folder.rglob("*.pdf"))  # Changed from glob to rglob
        
        if not pdf_files:
            self.logger.warning(f"No PDF files found in {self.base_folder}")
            return results
            
        self.logger.info(f"Found {len(pdf_files)} PDF files to process")
        
        successful_extractions = 0
        
        # Process each PDF file
        for pdf_file in pdf_files:
            try:
                # Use relative path as key for better organization
                relative_path = pdf_file.relative_to(self.base_folder)
                key = str(relative_path)
                
                # Extract text using the extract_file method
                text_content = self.extract_file(str(pdf_file))
                results[key] = text_content
                successful_extractions += 1
                
            except Exception as e:
                # Store error message instead of failing completely
                relative_path = pdf_file.relative_to(self.base_folder)
                key = str(relative_path)
                error_msg = f"[ERROR] Could not extract: {e}"
                results[key] = error_msg
                self.logger.error(f"Failed to extract {pdf_file}: {e}")
                
        self.logger.info(f"Extraction completed: {successful_extractions}/{len(pdf_files)} successful")
        
        return results