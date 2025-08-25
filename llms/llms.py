from typing import List, Dict, Optional
from providers import *

class ProviderFactory:
    """Factory class for creating LLM providers."""
    
    # Registry of available providers
    ONLINE_PROVIDERS = {
        "openai": OpenAIProvider,
        "gemini": GoogleProvider,
        "google": GoogleProvider,
        "together": TogetherProvider,
        "anthropic": AnthropicProvider,
        "claude": AnthropicProvider,
    }
    
    OFFLINE_PROVIDERS = {
        "ollama": OllamaProvider,
        "vllm": VLLMProvider,
        "huggingface": HuggingFaceProvider,
        "onnx": ONNXProvider,
    }
    
    @classmethod
    def create_online_provider(cls, model_name: str, api_key: str, model_version: str, 
                             base_url: Optional[str] = None, **kwargs) -> OnlineProvider:
        """Create an online provider instance."""
        model_name = model_name.lower()
        
        if model_name not in cls.ONLINE_PROVIDERS:
            available_providers = ", ".join(cls.ONLINE_PROVIDERS.keys())
            raise ValueError(f"Unsupported online provider: {model_name}. Available: {available_providers}")
        
        provider_class = cls.ONLINE_PROVIDERS[model_name]
        
        # Handle special cases that require additional parameters
        if model_name == "together":
            if not base_url:
                raise ValueError("base_url is required for Together AI provider")
            return provider_class(api_key, model_version, base_url, **kwargs)
        else:
            return provider_class(api_key, model_version, **kwargs)
    
    @classmethod
    def create_offline_provider(cls, engine: str, model_version: str, 
                              base_url: Optional[str] = None, model_path: Optional[str] = None, 
                              tokenizer_path: Optional[str] = None, **kwargs) -> OfflineProvider:
        """Create an offline provider instance."""
        engine = engine.lower()
        
        if engine not in cls.OFFLINE_PROVIDERS:
            available_providers = ", ".join(cls.OFFLINE_PROVIDERS.keys())
            raise ValueError(f"Unsupported offline provider: {engine}. Available: {available_providers}")
        
        provider_class = cls.OFFLINE_PROVIDERS[engine]
        
        # Handle special cases that require additional parameters
        if engine in ["ollama", "vllm"]:
            if not base_url:
                raise ValueError(f"base_url is required for {engine} provider")
            return provider_class(model_version, base_url, **kwargs)
        elif engine == "onnx":
            if not model_path:
                raise ValueError("model_path is required for ONNX provider")
            return provider_class(model_version, model_path, tokenizer_path, **kwargs)
        else:  # huggingface
            return provider_class(model_version, **kwargs)
    
    @classmethod
    def get_available_providers(cls) -> Dict[str, List[str]]:
        """Get list of all available providers."""
        return {
            "online": list(cls.ONLINE_PROVIDERS.keys()),
            "offline": list(cls.OFFLINE_PROVIDERS.keys())
        }


class LLMs:
    """Main LLM interface class using Factory pattern and OOP principles."""
    
    def __init__(self, type: str, model_version: str, model_name: Optional[str] = None, 
                 engine: Optional[str] = None, api_key: Optional[str] = None, 
                 base_url: Optional[str] = None, model_path: Optional[str] = None, 
                 tokenizer_path: Optional[str] = None, **kwargs):
        """Initialize LLM provider with the provided configuration.
        
        Args:
            type: "offline" or "online"
            model_version: Model version/name
            model_name: Provider name for online models ("openai", "gemini", "together", "anthropic")
            engine: Engine type for offline models ("ollama", "vllm", "huggingface", "onnx")
            api_key: API key for online models
            base_url: Base URL for API endpoints
            model_path: Path to model file (for ONNX)
            tokenizer_path: Path to tokenizer (for ONNX)
            **kwargs: Additional parameters (max_tokens, temperature, top_p, etc.)
        """
        self.type = type.lower()
        self.model_version = model_version
        self.provider: BaseProvider = self._create_provider(
            model_name, engine, api_key, base_url, model_path, tokenizer_path, **kwargs
        )
    
    def _create_provider(self, model_name: Optional[str], engine: Optional[str], 
                        api_key: Optional[str], base_url: Optional[str], 
                        model_path: Optional[str], tokenizer_path: Optional[str], 
                        **kwargs) -> BaseProvider:
        """Create appropriate provider based on type."""
        if self.type == "online":
            if not model_name:
                raise ValueError("model_name is required for online providers")
            return ProviderFactory.create_online_provider(
                model_name, api_key, self.model_version, base_url, **kwargs
            )
        elif self.type == "offline":
            if not engine:
                raise ValueError("engine is required for offline providers")
            return ProviderFactory.create_offline_provider(
                engine, self.model_version, base_url, model_path, tokenizer_path, **kwargs
            )
        else:
            raise ValueError(f"Unsupported LLM type: {self.type}. Use 'online' or 'offline'")
    
    def generate_content(self, prompt: List[Dict[str, str]]) -> str:
        """Generate content using the initialized LLM provider.
        
        Args:
            prompt: List of message dictionaries with 'role' and 'content' keys
            
        Returns:
            Generated content
        """
        return self.provider.generate_content(prompt)
    
    def get_provider_info(self) -> Dict[str, any]:
        """Get information about the current provider."""
        return {
            "type": self.type,
            "provider_class": self.provider.__class__.__name__,
            "model_version": self.model_version,
            "max_tokens": getattr(self.provider, 'max_tokens', None),
            "temperature": getattr(self.provider, 'temperature', None),
            "top_p": getattr(self.provider, 'top_p', None),
        }
    
    def update_generation_params(self, **kwargs) -> None:
        """Update generation parameters dynamically.
        
        Args:
            **kwargs: Parameters to update (max_tokens, temperature, top_p)
        """
        for key, value in kwargs.items():
            if hasattr(self.provider, key):
                setattr(self.provider, key, value)
            else:
                print(f"Warning: Parameter '{key}' not supported by {self.provider.__class__.__name__}")
    
    @staticmethod
    def get_available_providers() -> Dict[str, List[str]]:
        """Get list of all available providers."""
        return ProviderFactory.get_available_providers()
    
    def __str__(self) -> str:
        return f"LLMs(type='{self.type}', provider={self.provider})"
    
    def __repr__(self) -> str:
        return self.__str__()