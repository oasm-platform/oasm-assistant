"""
Batch processing pipeline for document embeddings.

This module provides a high-level interface for processing documents through
multiple stages: metadata extraction, text preprocessing, and text chunking.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Iterator, Tuple
from dataclasses import dataclass
from common.logger import logger


from .metadata_extractor import MetadataExtractor
from .text_preprocessor import TextPreprocessor
from .chunk_processor import SentenceChunker, SentenceChunkerConfig


@dataclass
class ProcessedChunk:
    """Container for a processed text chunk with its metadata."""
    text: str
    metadata: Dict[str, Any]
    chunk_id: str
    document_id: str

class BatchProcessor:
    """
    Main class for processing documents through the pipeline.
    
    The processing pipeline consists of:
    1. Metadata extraction
    2. Text preprocessing
    3. Text chunking
    """
    
    def __init__(
        self,
        max_chunk_tokens: int = 500,
        chunk_overlap: int = 50,
        use_tiktoken: bool = True
    ):
        """
        Initialize the document processor.
        
        Args:
            max_chunk_tokens: Maximum number of tokens per chunk
            chunk_overlap: Number of overlapping tokens between chunks
            use_tiktoken: Whether to use tiktoken for token counting (more accurate)
        """
        self.metadata_extractor = MetadataExtractor()
        self.text_preprocessor = TextPreprocessor()
        
        # Configure chunker
        chunker_config = SentenceChunkerConfig(
            max_tokens=max_chunk_tokens,
            overlap_tokens=chunk_overlap,
            tiktoken_encoding="cl100k_base" if use_tiktoken else None
        )
        self.chunker = SentenceChunker(config=chunker_config)
    
    def process_file(self, file_path: str) -> List[ProcessedChunk]:
        """
        Process a single file through the pipeline.
        
        Args:
            file_path: Path to the file to process
            
        Returns:
            List of processed chunks with metadata
        """
        try:
            # 1. Extract metadata
            metadata = self.metadata_extractor.extract_metadata(file_path)
            document_id = metadata.get('file_name', os.path.basename(file_path))
            
            # Read file content (assuming text content for now)
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
            
            # 2. Preprocess text
            clean_text = self.text_preprocessor.preprocess(text)
            
            # 3. Chunk text
            chunks = self.chunker.chunk(clean_text)
            
            # 4. Create processed chunks with metadata
            processed_chunks = []
            for i, chunk in enumerate(chunks):
                chunk_metadata = metadata.copy()
                chunk_metadata.update({
                    'chunk_id': f"{document_id}_chunk_{i}",
                    'chunk_index': i,
                    'total_chunks': len(chunks),
                    'chunk_tokens': chunk.n_tokens
                })
                
                processed_chunks.append(ProcessedChunk(
                    text=chunk.text,
                    metadata=chunk_metadata,
                    chunk_id=chunk_metadata['chunk_id'],
                    document_id=document_id
                ))
            
            logger.info(f"Processed {file_path}: {len(processed_chunks)} chunks created")
            return processed_chunks
            
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {str(e)}")
            raise

    def process_directory(
        self,
        input_dir: str,
        output_dir: Optional[str] = None,
        file_extensions: List[str] = None
    ) -> Iterator[Tuple[str, List[ProcessedChunk]]]:
        """
        Process all files in a directory.
        
        Args:
            input_dir: Directory containing files to process
            output_dir: Optional directory to save processed chunks
            file_extensions: List of file extensions to process (e.g., ['.pdf', '.txt'])
            
        Yields:
            Tuples of (file_path, list_of_processed_chunks)
        """
        if file_extensions is None:
            file_extensions = ['.pdf', '.txt', '.md']
        
        input_path = Path(input_dir)
        output_path = Path(output_dir) if output_dir else None
        
        # Create output directory if it doesn't exist
        if output_path and not output_path.exists():
            output_path.mkdir(parents=True, exist_ok=True)
        
        # Process each file in the directory
        for ext in file_extensions:
            for file_path in input_path.glob(f"*{ext}"):
                try:
                    chunks = self.process_file(str(file_path))
                    if output_path:
                        self._save_chunks(chunks, output_path)
                    yield str(file_path), chunks
                except Exception as e:
                    logger.error(f"Failed to process {file_path}: {str(e)}")
                    continue

    def _save_chunks(
        self,
        chunks: List[ProcessedChunk],
        output_dir: Path
    ) -> None:
        """
        Save processed chunks to disk.
        
        Args:
            chunks: List of processed chunks
            output_dir: Directory to save chunks
        """
        for chunk in chunks:
            output_file = output_dir / f"{chunk.chunk_id}.json"
            try:
                import json
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        'text': chunk.text,
                        'metadata': chunk.metadata
                    }, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"Failed to save chunk {chunk.chunk_id}: {str(e)}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Process documents for embeddings.')
    parser.add_argument('input', help='Input file or directory')
    parser.add_argument('--output', help='Output directory (optional)')
    parser.add_argument('--max-tokens', type=int, default=500,
                       help='Maximum tokens per chunk')
    parser.add_argument('--overlap', type=int, default=50,
                       help='Number of overlapping tokens between chunks')
    
    args = parser.parse_args()
    
    # Initialize processor
    processor = DocumentProcessor(
        max_chunk_tokens=args.max_tokens,
        chunk_overlap=args.overlap
    )
    
    # Process input
    input_path = Path(args.input)
    if input_path.is_file():
        chunks = processor.process_file(args.input)
        if args.output:
            output_dir = Path(args.output)
            output_dir.mkdir(parents=True, exist_ok=True)
            processor._save_chunks(chunks, output_dir)
        print(f"Processed {len(chunks)} chunks from {args.input}")
    elif input_path.is_dir():
        for file_path, chunks in processor.process_directory(
            args.input, args.output
        ):
            print(f"Processed {len(chunks)} chunks from {file_path}")
    else:
        print(f"Error: {args.input} is not a valid file or directory")

