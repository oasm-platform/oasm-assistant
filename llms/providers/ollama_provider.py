"""
Ollama models
"""
import requests
from typing import List, Dict
from .base_provider import ServerBasedProvider

class OllamaProvider(ServerBasedProvider):
    """Ollama local server provider implementation."""
    
    def __init__(self, model_version: str, base_url: str, **kwargs):
        """Initialize Ollama provider.
        
        Args:
            model_version: Ollama model name
            base_url: Ollama server URL
            **kwargs: Additional configuration
        """
        self.session = None
        super().__init__(model_version, base_url, **kwargs)
    
    def _check_server_connection(self) -> bool:
        """Check if Ollama server is accessible."""
        try:
            response = requests.get(self.base_url, timeout=5)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException:
            return False
    
    def _initialize(self, **kwargs) -> None:
        """Initialize Ollama connection and pull model if needed."""
        super()._initialize(**kwargs)
        
        try:
            print("Connected to Ollama API server successfully.")
            self.session = requests.Session()
            self._ensure_model_available()
        except Exception as e:
            raise ConnectionError(f"Error initializing Ollama provider: {e}")
    
    def _ensure_model_available(self) -> None:
        """Ensure the specified model is available, pull if needed."""
        try:
            # Check if model exists
            response = self.session.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            
            models = response.json().get("models", [])
            model_exists = any(self.model_version in m["name"] for m in models)

            if not model_exists:
                print(f"Model '{self.model_version}' not found. Pulling...")
                self._pull_model()
            else:
                print(f"Model '{self.model_version}' already exists.")
                
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Error checking Ollama models: {e}")
    
    def _pull_model(self) -> None:
        """Pull model from Ollama registry."""
        try:
            pull_data = {"name": self.model_version}
            response = self.session.post(f"{self.base_url}/api/pull", json=pull_data)
            response.raise_for_status()
            print(f"Model '{self.model_version}' pulled successfully.")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Error pulling model: {e}")
    
    def _generate_raw_content(self, prompt: List[Dict[str, str]]) -> str:
        """Generate content using Ollama API."""
        if not self.session:
            raise RuntimeError("Ollama session not initialized.")

        print(f"Generating content with Ollama model '{self.model_version}'...")

        try:
            payload = {
                "model": self.model_version,
                "messages": prompt,
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "top_p": self.top_p,
                    "num_predict": self.max_tokens
                }
            }
            
            response = self.session.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            
            response_data = response.json()
            return response_data["message"]["content"].strip()

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Ollama API request error: {e}")
        except KeyError as e:
            raise RuntimeError(f"Unexpected response format from Ollama: {e}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error during content generation: {e}")
            
        return self.remove_think_blocks(response_data["message"]["content"].strip())
