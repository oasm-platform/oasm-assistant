"""
OpenAI GPT models
"""

import openai
from typing import List, Dict
from .base_provider import OnlineProvider

class OpenAIProvider(OnlineProvider):
    """OpenAI API provider implementation."""
    
    def __init__(self, api_key: str, model_version: str, **kwargs):
        """Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key
            model_version: OpenAI model version (e.g., 'gpt-4', 'gpt-3.5-turbo')
            **kwargs: Additional configuration
        """
        self.client = None
        super().__init__(model_version, api_key, **kwargs)
    
    def _initialize(self, **kwargs) -> None:
        """Initialize OpenAI client."""
        try:
            self.client = openai.OpenAI(api_key=self.api_key)
            # Test connection with a minimal request
            self.client.models.list()
        except Exception as e:
            raise ConnectionError(f"Failed to initialize OpenAI client: {e}")
    
    def _generate_raw_content(self, prompt: List[Dict[str, str]]) -> str:
        """Generate content using OpenAI API."""
        try:
            response = self.client.chat.completions.create(
                model=self.model_version,
                messages=prompt,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                top_p=self.top_p
            )
            return response.choices[0].message.content
        except openai.APIError as e:
            raise RuntimeError(f"OpenAI API error: {e}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error during content generation: {e}")