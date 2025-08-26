import requests
from typing import List, Dict
from .base_provider import ServerBasedProvider

class VLLMProvider(ServerBasedProvider):
    """vLLM server provider implementation."""
    
    def __init__(self, model_version: str, base_url: str, **kwargs):
        """Initialize vLLM provider.
        
        Args:
            model_version: vLLM model name
            base_url: vLLM server URL
            **kwargs: Additional configuration
        """
        self.session = None
        super().__init__(model_version, base_url, **kwargs)
    
    def _check_server_connection(self) -> bool:
        """Check if vLLM server is accessible."""
        try:
            response = requests.get(f"{self.base_url}/v1/models", timeout=10)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException:
            return False
    
    def _initialize(self, **kwargs) -> None:
        """Initialize vLLM connection and validate model."""
        super()._initialize(**kwargs)
        
        try:
            self.session = requests.Session()
            self._validate_model()
            print("Connected to vLLM API server successfully.")
        except Exception as e:
            raise ConnectionError(f"Error initializing vLLM provider: {e}")
    
    def _validate_model(self) -> None:
        """Validate model availability and get model info."""
        try:
            response = self.session.get(f"{self.base_url}/v1/models", timeout=10)
            response.raise_for_status()
            
            models = response.json().get("data", [])
            matched_model = next((m for m in models if m["id"] == self.model_version), None)

            if matched_model:
                # Update max_tokens from model info if available
                model_max_tokens = matched_model.get("max_model_len", self.max_tokens)
                self.max_tokens = min(self.max_tokens, model_max_tokens)
                print(f"Model '{self.model_version}' found with max_tokens: {self.max_tokens}")
            else:
                print(f"Warning: Model '{self.model_version}' not found in vLLM model list. Proceeding with default settings.")

        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Error validating vLLM model: {e}")
    
    def _generate_raw_content(self, prompt: List[Dict[str, str]]) -> str:
        """Generate content using vLLM API."""
        if not self.session:
            raise RuntimeError("vLLM session not initialized.")

        print(f"Generating content with vLLM model '{self.model_version}'...")

        try:
            payload = {
                "model": self.model_version,
                "messages": prompt,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "top_p": self.top_p
            }
            
            response = self.session.post(
                f"{self.base_url}/v1/chat/completions",
                headers={"Content-Type": "application/json"},
                json=payload
            )
            response.raise_for_status()
            
            response_data = response.json()
            return response_data["choices"][0]["message"]["content"].strip()

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"vLLM API request error: {e}")
        except KeyError as e:
            raise RuntimeError(f"Unexpected response format from vLLM: {e}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error during content generation: {e}")