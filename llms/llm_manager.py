from typing import List, Dict, Any, Optional
from langchain_core.language_models import BaseLanguageModel
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.chat_models import ChatOllama
from common.logger import logger


class LLMConfig:
    """Configuration class for LLM providers"""
    
    def __init__(self, 
                 provider: str,
                 api_key: str = None,
                 model_name: str = None,
                 temperature: float = 0.1,
                 max_tokens: int = 4000,
                 timeout: int = 60,
                 max_retries: int = 3,
                 base_url: str = None,
                 **kwargs):
        self.provider = provider
        self.api_key = api_key
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_url = base_url
        self.extra_params = kwargs


class LLMManager:
    """LLM Manager with LangChain integration and external configuration"""
    
    def __init__(self, 
                 configs: Dict[str, LLMConfig] = None,
                 default_provider: str = None,
                 enable_ollama: bool = True):
        """
        Initialize LLM Manager with configurations
        
        Args:
            configs: Dictionary of provider configurations {provider_name: LLMConfig}
            default_provider: Default provider to use
            enable_ollama: Whether to enable Ollama (local) provider
        """
        self.configs = configs or {}
        self.providers = {}
        self.default_provider = default_provider
        self.enable_ollama = enable_ollama
        
        self._initialize_providers()
        
        # Set default provider if not specified
        if not self.default_provider and self.providers:
            self.default_provider = list(self.providers.keys())[0]

    
    def _initialize_providers(self):
        """Initialize available LLM providers based on configurations"""
        try:
            # Initialize configured providers
            for provider_name in self.configs:
                self._initialize_single_provider(provider_name)
            
            # Always add Ollama if enabled (doesn't require API key)
            if self.enable_ollama and "ollama" not in self.configs:
                self.providers["ollama"] = self._create_ollama_provider
            
            if not self.providers:
                logger.warning("No LLM providers available. Check configurations.")
                
        except Exception as e:
            logger.error(f"Error initializing LLM providers: {e}")
            raise
    
    def _initialize_single_provider(self, provider: str):
        """Initialize a single provider"""
        config = self.configs.get(provider)
        if not config:
            return
            
        if config.provider == "openai":
            self.providers["openai"] = self._create_openai_provider
        elif config.provider == "anthropic":
            self.providers["anthropic"] = self._create_anthropic_provider
        elif config.provider == "google":
            self.providers["google"] = self._create_google_provider
        elif config.provider == "ollama":
            self.providers["ollama"] = self._create_ollama_provider
        else:
            logger.warning(f"Unknown provider: {config.provider}")
    
    def _create_openai_provider(self, model: str = None, **kwargs) -> BaseLanguageModel:
        """Create OpenAI LangChain provider"""
        config = self.configs.get("openai")
        if not config:
            raise ValueError("OpenAI configuration not found")
            
        return ChatOpenAI(
            api_key=config.api_key,
            model=model or config.model_name or "gpt-3.5-turbo",
            temperature=kwargs.get("temperature", config.temperature),
            max_tokens=kwargs.get("max_tokens", config.max_tokens),
            timeout=kwargs.get("timeout", config.timeout),
            max_retries=kwargs.get("max_retries", config.max_retries),
            **config.extra_params
        )
    
    def _create_anthropic_provider(self, model: str = None, **kwargs) -> BaseLanguageModel:
        """Create Anthropic LangChain provider with compatibility handling"""
        config = self.configs.get("anthropic")
        if not config:
            raise ValueError("Anthropic configuration not found")
            
        params = {
            "api_key": config.api_key,
            "model": model or config.model_name or "claude-3-sonnet-20240229",
            "temperature": kwargs.get("temperature", config.temperature),
            **config.extra_params
        }
        
        max_tokens = kwargs.get("max_tokens", config.max_tokens)
        
        # Handle version differences in Anthropic API
        try:
            return ChatAnthropic(
                **params,
                max_tokens=max_tokens,
                timeout=kwargs.get("timeout", config.timeout),
                max_retries=kwargs.get("max_retries", config.max_retries)
            )
        except TypeError:
            return ChatAnthropic(
                **params,
                max_tokens_to_sample=max_tokens,
                timeout=kwargs.get("timeout", config.timeout),
                max_retries=kwargs.get("max_retries", config.max_retries)
            )
    
    def _create_google_provider(self, model: str = None, **kwargs) -> BaseLanguageModel:
        """Create Google LangChain provider with compatibility handling"""
        config = self.configs.get("google")
        if not config:
            raise ValueError("Google configuration not found")
            
        params = {
            "google_api_key": config.api_key,
            "model": model or config.model_name or "gemini-pro",
            "temperature": kwargs.get("temperature", config.temperature),
            **config.extra_params
        }
        
        max_tokens = kwargs.get("max_tokens", config.max_tokens)
        
        try:
            return ChatGoogleGenerativeAI(
                **params,
                max_output_tokens=max_tokens
            )
        except TypeError:
            # Fallback for different versions
            return ChatGoogleGenerativeAI(
                **params,
                max_tokens=max_tokens
            )
    
    def _create_ollama_provider(self, model: str = None, **kwargs) -> BaseLanguageModel:
        """Create Ollama LangChain provider with compatibility handling"""
        config = self.configs.get("ollama")
        
        # Use config if available, otherwise use defaults
        if config:
            base_model = config.model_name or "llama2"
            base_temp = config.temperature
            base_url = config.base_url or "http://localhost:11434"
            extra_params = config.extra_params
        else:
            base_model = "llama2"
            base_temp = 0.1
            base_url = "http://localhost:11434"
            extra_params = {}
        
        params = {
            "model": model or base_model,
            "temperature": kwargs.get("temperature", base_temp),
            "base_url": kwargs.get("base_url", base_url),
            **extra_params
        }
        
        # Handle version differences in Ollama API
        if "timeout" in kwargs:
            try:
                return ChatOllama(**params, timeout=kwargs["timeout"])
            except TypeError:
                return ChatOllama(**params)
        else:
            return ChatOllama(**params)
    
    def get_llm(self, provider: str = None, model: str = None, **kwargs) -> BaseLanguageModel:
        """Get an LLM instance"""
        provider = provider or self.default_provider
        
        if not provider:
            raise ValueError("No provider specified and no default provider set")
            
        if provider not in self.providers:
            available = list(self.providers.keys())
            error_msg = f"Provider '{provider}' not available. Available: {available}"
            raise ValueError(error_msg)
        
        return self.providers[provider](model, **kwargs)
    
    def get_available_providers(self) -> List[str]:
        """Get list of available providers"""
        return list(self.providers.keys())
    
    def set_default_provider(self, provider: str):
        """Set the default provider"""
        if provider in self.providers:
            self.default_provider = provider
        else:
            available = list(self.providers.keys())
            error_msg = f"Provider '{provider}' not available. Available: {available}"
            raise ValueError(error_msg)
    
    def get_provider_config(self, provider: str) -> Optional[LLMConfig]:
        """Get configuration for a provider"""
        return self.configs.get(provider)






