"""
Google Gemini models
"""

import google.generativeai as genai
from typing import List, Dict
from .base_provider import OnlineProvider

class GoogleProvider(OnlineProvider):
    """Google Gemini API provider implementation."""
    
    def __init__(self, api_key: str, model_version: str, **kwargs):
        """Initialize Google Gemini provider.
        
        Args:
            api_key: Google API key
            model_version: Gemini model version (e.g., 'gemini-pro', 'gemini-pro-vision')
            **kwargs: Additional configuration
        """
        self.model = None
        super().__init__(model_version, api_key, **kwargs)
    
    def _initialize(self, **kwargs) -> None:
        """Initialize Google Gemini client."""
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(model_name=self.model_version)
            # Test connection
            self.model.count_tokens("test")
        except Exception as e:
            raise ConnectionError(f"Failed to initialize Google Gemini client: {e}")
    
    def _convert_to_gemini_format(self, prompt: List[Dict[str, str]]) -> List[Dict[str, any]]:
        """Convert standard prompt format to Gemini format."""
        gemini_messages = []
        for msg in prompt:
            gemini_messages.append({
                "role": msg["role"],
                "parts": [msg["content"]]
            })
        return gemini_messages
    
    def _generate_raw_content(self, prompt: List[Dict[str, str]]) -> str:
        """Generate content using Google Gemini API."""
        try:
            gemini_messages = self._convert_to_gemini_format(prompt)
            response = self.model.generate_content(gemini_messages)
            
            # Handle different response formats
            try:
                return response.text
            except Exception:
                return response.candidates[0].content.parts[0].text
                
        except Exception as e:
            raise RuntimeError(f"Google Gemini API error: {e}")