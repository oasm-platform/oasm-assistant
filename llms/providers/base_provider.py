from abc import ABC, abstractmethod
import re
from typing import List, Dict, Optional, Any

class BaseProvider(ABC):
    """Abstract base class for all LLM providers."""
    
    def __init__(self, model_version: str, **kwargs):
        """Initialize base provider.
        
        Args:
            model_version (str): Model version/name
            **kwargs: Additional configuration parameters
        """
        self.model_version = model_version
        self.max_tokens = kwargs.get('max_tokens', 4096)
        self.temperature = kwargs.get('temperature', 0.7)
        self.top_p = kwargs.get('top_p', 0.9)
        self._is_initialized = False
        
    @abstractmethod
    def _initialize(self, **kwargs) -> None:
        """Initialize the provider-specific client/model."""
        pass
    
    @abstractmethod
    def _generate_raw_content(self, prompt: List[Dict[str, str]]) -> str:
        """Generate raw content without post-processing.
        
        Args:
            prompt: List of message dictionaries
            
        Returns:
            Raw generated content
        """
        pass
    
    def remove_think_blocks(self, text: str) -> str:
        """Remove <think> blocks and their content from text.
        
        Args:
            text: Input text that may contain think blocks
            
        Returns:
            Cleaned text without think blocks
        """
        pattern = r'<think>.*?</think>'
        cleaned_text = re.sub(pattern, '', text, flags=re.DOTALL)
        cleaned_text = re.sub(r'\n\s*\n', '\n', cleaned_text).strip()
        return cleaned_text
    
    def validate_prompt(self, prompt: List[Dict[str, str]]) -> None:
        """Validate prompt format.
        
        Args:
            prompt: List of message dictionaries
            
        Raises:
            ValueError: If prompt format is invalid
        """
        if not isinstance(prompt, list):
            raise ValueError("Prompt must be a list of dictionaries")
        
        for i, msg in enumerate(prompt):
            if not isinstance(msg, dict):
                raise ValueError(f"Message at index {i} must be a dictionary")
            
            if 'role' not in msg or 'content' not in msg:
                raise ValueError(f"Message at index {i} must have 'role' and 'content' keys")
    
    def generate_content(self, prompt: List[Dict[str, str]]) -> str:
        """Generate content using the provider.
        
        Args:
            prompt: List of message dictionaries
            
        Returns:
            Generated and cleaned content
        """
        if not self._is_initialized:
            raise RuntimeError("Provider not initialized. Call _initialize() first.")
        
        self.validate_prompt(prompt)
        raw_content = self._generate_raw_content(prompt)
        return self.remove_think_blocks(raw_content)
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model_version='{self.model_version}')"


class OnlineProvider(BaseProvider):
    """Base class for online API providers."""
    
    def __init__(self, model_version: str, api_key: str, **kwargs):
        """Initialize online provider.
        
        Args:
            model_version: Model version/name
            api_key: API key for authentication
            **kwargs: Additional configuration parameters
        """
        super().__init__(model_version, **kwargs)
        self.api_key = api_key
        if not self.api_key:
            raise ValueError("API key is required for online providers")
        self._initialize(**kwargs)
        self._is_initialized = True


class OfflineProvider(BaseProvider):
    """Base class for offline/local providers."""
    
    def __init__(self, model_version: str, **kwargs):
        """Initialize offline provider.
        
        Args:
            model_version: Model version/name
            **kwargs: Additional configuration parameters
        """
        super().__init__(model_version, **kwargs)
        self._initialize(**kwargs)
        self._is_initialized = True


class ServerBasedProvider(OfflineProvider):
    """Base class for server-based offline providers (Ollama, vLLM)."""
    
    def __init__(self, model_version: str, base_url: str, **kwargs):
        """Initialize server-based provider.
        
        Args:
            model_version: Model version/name
            base_url: Server base URL
            **kwargs: Additional configuration parameters
        """
        self.base_url = base_url
        if not self.base_url:
            raise ValueError("Base URL is required for server-based providers")
        super().__init__(model_version, **kwargs)
    
    @abstractmethod
    def _check_server_connection(self) -> bool:
        """Check if server is accessible."""
        pass
    
    def _initialize(self, **kwargs) -> None:
        """Initialize server connection."""
        if not self._check_server_connection():
            raise ConnectionError(f"Cannot connect to server at {self.base_url}")