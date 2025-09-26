from typing import List, Dict, Any, Optional
from langchain_core.language_models import BaseLanguageModel
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.chat_models import ChatOllama
from common.logger import logger
from common.config import LlmConfigs


class LLMManager:
    """LLM Manager with LangChain integration and external configuration"""

    def __init__(self,
                 config: LlmConfigs):
        """
        Initialize LLM Manager with configurations

        Args:
            config: LlmConfigs instance with provider configuration
        """
        self.config = config
        self.providers = {}

        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize available LLM providers based on configurations"""
        try:
            # Initialize configured provider if available
            if self.config.provider and self.config.api_key:
                self._initialize_single_provider(self.config.provider)

            if not self.providers:
                logger.warning("No LLM providers available. Check configurations.")

        except Exception as e:
            logger.error(f"Error initializing LLM providers: {e}")
            raise

    def _initialize_single_provider(self, provider: str):
        """Initialize a single provider"""
        if provider == "openai":
            self.providers["openai"] = self._create_openai_provider
        elif provider == "anthropic":
            self.providers["anthropic"] = self._create_anthropic_provider
        elif provider == "google":
            self.providers["google"] = self._create_google_provider
        elif provider == "ollama":
            self.providers["ollama"] = self._create_ollama_provider
        else:
            logger.warning(f"Unknown provider: {provider}")

    def _create_openai_provider(self, model: str = None, **kwargs) -> BaseLanguageModel:
        """Create OpenAI LangChain provider"""
        if self.config.provider != "openai" or not self.config.api_key:
            raise ValueError("OpenAI configuration not found or invalid")

        return ChatOpenAI(
            api_key=self.config.api_key,
            model=model or self.config.model_name or "gpt-3.5-turbo",
            temperature=kwargs.get("temperature", self.config.temperature),
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            timeout=kwargs.get("timeout", self.config.timeout),
            max_retries=kwargs.get("max_retries", self.config.max_retries),
            **self.config.extra_params
        )

    def _create_anthropic_provider(self, model: str = None, **kwargs) -> BaseLanguageModel:
        """Create Anthropic LangChain provider with compatibility handling"""
        if self.config.provider != "anthropic" or not self.config.api_key:
            raise ValueError("Anthropic configuration not found or invalid")

        params = {
            "api_key": self.config.api_key,
            "model": model or self.config.model_name or "claude-3-sonnet-20240229",
            "temperature": kwargs.get("temperature", self.config.temperature),
            **self.config.extra_params
        }

        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)

        # Handle version differences in Anthropic API
        try:
            return ChatAnthropic(
                **params,
                max_tokens=max_tokens,
                timeout=kwargs.get("timeout", self.config.timeout),
                max_retries=kwargs.get("max_retries", self.config.max_retries)
            )
        except TypeError:
            return ChatAnthropic(
                **params,
                max_tokens_to_sample=max_tokens,
                timeout=kwargs.get("timeout", self.config.timeout),
                max_retries=kwargs.get("max_retries", self.config.max_retries)
            )

    def _create_google_provider(self, model: str = None, **kwargs) -> BaseLanguageModel:
        """Create Google LangChain provider with compatibility handling"""
        if self.config.provider != "google" or not self.config.api_key:
            raise ValueError("Google configuration not found or invalid")

        params = {
            "google_api_key": self.config.api_key,
            "model": model or self.config.model_name or "gemini-pro",
            "temperature": kwargs.get("temperature", self.config.temperature),
            **self.config.extra_params
        }

        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)

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
        # Use config if provider is ollama, otherwise use defaults
        if self.config.provider == "ollama":
            base_model = self.config.model_name or "llama2"
            base_temp = self.config.temperature
            base_url = self.config.base_url or "http://localhost:11434"
            extra_params = self.config.extra_params
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
        # Use the configured default provider if no provider is specified
        if not provider:
            provider = self.config.provider

        if not provider:
            raise ValueError("No provider specified")

        if provider not in self.providers:
            available = list(self.providers.keys())
            error_msg = f"Provider '{provider}' not available. Available: {available}"
            raise ValueError(error_msg)

        return self.providers[provider](model, **kwargs)

    def get_available_providers(self) -> List[str]:
        """Get list of available providers"""
        return list(self.providers.keys())


    def get_provider_config(self, provider: str) -> Optional[LlmConfigs]:
        """Get configuration for a provider"""
        if provider == self.config.provider:
            return self.config
        return None