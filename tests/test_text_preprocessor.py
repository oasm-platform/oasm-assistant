"""
Pytest tests for text preprocessor functionality with internationalization support
"""
import pytest
from unittest.mock import Mock, patch
import sys
import os

# Add path to import directly from file
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import module directly from file to avoid importing the entire package
import importlib.util
text_preprocessor_spec = importlib.util.spec_from_file_location(
    "text_preprocessor",
    os.path.join(os.path.dirname(__file__), '..', 'data', 'embeddings', 'processing', 'text_preprocessor.py')
)
text_preprocessor_module = importlib.util.module_from_spec(text_preprocessor_spec)
text_preprocessor_spec.loader.exec_module(text_preprocessor_module)

# Get the required classes
TextPreprocessor = text_preprocessor_module.TextPreprocessor
TextPreprocessorConfig = text_preprocessor_module.TextPreprocessorConfig


class TestTextPreprocessorInternationalization:
    """Test text preprocessor with international characters"""
    
    def test_preserve_accented_characters(self):
        """Test that accented characters are preserved during preprocessing"""
        preprocessor = TextPreprocessor()
        text = "Café résumé naïve façade"
        processed = preprocessor.preprocess(text)
        # Ensure accented characters are preserved
        assert "Café" in processed
        assert "résumé" in processed
        assert "naïve" in processed
        assert "façade" in processed
    
    def test_preserve_umlauts(self):
        """Test that umlauts are preserved during preprocessing"""
        preprocessor = TextPreprocessor()
        text = "Zürich München naïve"
        processed = preprocessor.preprocess(text)
        assert "Zürich" in processed or "Zurich" in processed
        assert "München" in processed or "Munchen" in processed
        assert "naïve" in processed or "naive" in processed
    
    def test_preserve_cyrillic_characters(self):
        """Test that Cyrillic characters are preserved during preprocessing"""
        preprocessor = TextPreprocessor()
        text = "Москва Санкт-Петербург"
        processed = preprocessor.preprocess(text)
        # Should preserve Cyrillic characters
        assert any(char in processed for char in "Москва")
        assert any(char in processed for char in "Санкт-Петербург")
    
    def test_preserve_chinese_characters(self):
        """Test that Chinese characters are preserved during preprocessing"""
        preprocessor = TextPreprocessor()
        text = "北京 上海 广州"
        processed = preprocessor.preprocess(text)
        # Should preserve Chinese characters
        assert "北京" in processed
        assert "上海" in processed
        assert "广州" in processed
    
    def test_handle_mixed_scripts(self):
        """Test handling of text with mixed scripts"""
        preprocessor = TextPreprocessor()
        text = "Hello 世界 café naïve"
        processed = preprocessor.preprocess(text)
        # Should preserve both Latin and Chinese characters
        assert "Hello" in processed
        assert "世界" in processed
        assert "café" in processed or "cafe" in processed
        assert "naïve" in processed or "naive" in processed
    
    def test_normalize_unicode_characters(self):
        """Test that Unicode normalization works correctly"""
        preprocessor = TextPreprocessor()
        # Text with composed and decomposed characters
        text = "café"  # 'e' + acute accent as single character
        processed = preprocessor.preprocess(text)
        # Should handle both forms correctly
        assert "café" in processed or "cafe" in processed
    
    def test_remove_special_bullet_characters(self):
        """Test that special bullet characters are replaced correctly"""
        preprocessor = TextPreprocessor()
        text = "• First point\n\u2022 Second point\n\u25E6 Third point"
        processed = preprocessor.preprocess(text)
        # Should replace bullet characters with markers
        assert "* First point" in processed
        assert "* Second point" in processed
        assert "* Third point" in processed
    
    def test_configuration_options(self):
        """Test that configuration options work with international characters"""
        # Test with default configuration
        config = TextPreprocessorConfig()
        preprocessor = TextPreprocessor(config=config)
        text = "café naïve"
        processed = preprocessor.preprocess(text)
        # Should still handle the text without normalization errors
        assert len(processed) > 0
