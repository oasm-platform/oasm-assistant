import requests
from typing import List, Dict
from .base_provider import OnlineProvider

class TogetherProvider(OnlineProvider):
    """Together AI API provider implementation."""
    
    def __init__(self, api_key: str, model_version: str, base_url: str, **kwargs):
        """Initialize Together AI provider.
        
        Args:
            api_key: Together AI API key
            model_version: Model version
            base_url: Together AI base URL
            **kwargs: Additional configuration
        """
        self.base_url = base_url
        self.headers = None
        self.session = None
        if not base_url:
            raise ValueError("Base URL is required for Together AI provider")
        super().__init__(model_version, api_key, **kwargs)
    
    def _initialize(self, **kwargs) -> None:
        """Initialize Together AI client."""
        try:
            self.headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            self.session = requests.Session()
            self.session.headers.update(self.headers)
            
            # Test connection
            test_url = f"{self.base_url}/v1/models"
            response = self.session.get(test_url, timeout=10)
            response.raise_for_status()
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Together AI: {e}")
    
    def _generate_raw_content(self, prompt: List[Dict[str, str]]) -> str:
        """Generate content using Together AI API."""
        try:
            data = {
                "model": self.model_version,
                "messages": prompt,
                "temperature": self.temperature,
                "top_p": self.top_p,
                "max_tokens": min(self.max_tokens, 512),  # Together AI limit
            }
            
            response = self.session.post(
                f"{self.base_url}/v1/chat/completions",
                json=data,
                timeout=60
            )
            response.raise_for_status()
            
            response_data = response.json()
            return response_data["choices"][0]["message"]["content"].strip()
            
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Together AI API request error: {e}")
        except KeyError as e:
            raise RuntimeError(f"Unexpected response format from Together AI: {e}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error during content generation: {e}")