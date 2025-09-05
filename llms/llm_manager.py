from typing import List

from langchain_core.language_models import BaseLanguageModel
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.chat_models import ChatOllama

from common.config import settings

from common.logger import logger

class LLMManager:
    """LLM Manager with LangChain integration"""

    def __init__(self):
        self.providers = {}
        self.default_provider = "openai"
        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize available LLM providers"""
        try:
            # OpenAI
            if getattr(settings, 'OPENAI_API_KEY', None):
                self.providers["openai"] = self._create_openai_provider

            # Anthropic
            if getattr(settings, 'ANTHROPIC_API_KEY', None):
                self.providers["anthropic"] = self._create_anthropic_provider
                self.providers["claude"] = self._create_anthropic_provider

            # Google
            if getattr(settings, 'GOOGLE_API_KEY', None):
                self.providers["google"] = self._create_google_provider
                self.providers["gemini"] = self._create_google_provider

            # Ollama (local) - always available
            self.providers["ollama"] = self._create_ollama_provider

            if not self.providers:
                logger.warning("No LLM providers available. Check API keys configuration.")

        except Exception as e:
            logger.error(f"Error initializing LLM providers: {e}")
            raise

    def _create_openai_provider(self, model: str = None, **kwargs) -> BaseLanguageModel:
        """Create OpenAI LangChain provider"""
        return ChatOpenAI(
            api_key=getattr(settings, 'OPENAI_API_KEY', ''),
            model=model or getattr(settings, 'LLM_MODEL', 'gpt-4'),
            temperature=kwargs.get("temperature", getattr(settings, 'LLM_TEMPERATURE', 0.1)),
            max_tokens=kwargs.get("max_tokens", getattr(settings, 'MAX_TOKENS', 4000)),
            timeout=kwargs.get("timeout", 60),
            max_retries=kwargs.get("max_retries", 3)
        )

    def _create_anthropic_provider(self, model: str = None, **kwargs) -> BaseLanguageModel:
        """Create Anthropic LangChain provider with compatibility handling"""
        params = {
            "api_key": getattr(settings, 'ANTHROPIC_API_KEY', ''),
            "model": model or "claude-3-sonnet-20240229",
            "temperature": kwargs.get("temperature", getattr(settings, 'LLM_TEMPERATURE', 0.1)),
        }

        max_tokens = kwargs.get("max_tokens", getattr(settings, 'MAX_TOKENS', 4000))
        # Handle version differences in Anthropic API
        try:
            return ChatAnthropic(
                **params,
                max_tokens=max_tokens,
                timeout=kwargs.get("timeout", 60),
                max_retries=kwargs.get("max_retries", 3)
            )
        except TypeError:
            return ChatAnthropic(
                **params,
                max_tokens_to_sample=max_tokens,
                timeout=kwargs.get("timeout", 60),
                max_retries=kwargs.get("max_retries", 3)
            )

    def _create_google_provider(self, model: str = None, **kwargs) -> BaseLanguageModel:
        """Create Google LangChain provider with compatibility handling"""
        params = {
            "google_api_key": getattr(settings, 'GOOGLE_API_KEY', ''),
            "model": model or "gemini-pro",
            "temperature": kwargs.get("temperature", getattr(settings, 'LLM_TEMPERATURE', 0.1)),
        }

        max_tokens = kwargs.get("max_tokens", getattr(settings, 'MAX_TOKENS', 4000))
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
        params = {
            "model": model or "llama2",
            "temperature": kwargs.get("temperature", getattr(settings, 'LLM_TEMPERATURE', 0.1)),
            "base_url": kwargs.get("base_url", "http://localhost:11434"),
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
