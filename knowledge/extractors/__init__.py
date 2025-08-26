from .pdf_extractor import PDFExtractor

def create_pdf_extractor(base_folder: str = "knowledge/documents/pdfs") -> PDFExtractor:
    """
    Create PDFExtractor instance
    
    Args:
        base_folder: Base directory for PDF files
        
    Returns:
        PDFExtractor instance
    """
    return PDFExtractor(base_folder)

__all__ = ['create_pdf_extractor', 'PDFExtractor']
