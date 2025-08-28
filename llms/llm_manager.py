"""
Enhanced LLM Manager for OASM Assistant with LangChain integration
Fixed version with compatibility handling
"""
from typing import List, Dict, Any
from datetime import datetime
from langchain_core.language_models import BaseLanguageModel
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.llms import Ollama
from langchain_core.messages import HumanMessage
from common.config.settings import settings


class LLMManager:
    """Enhanced LLM manager with LangChain integration for OASM Assistant"""

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
                print("No LLM providers available. Check API keys configuration.")

        except Exception as e:
            print(e)
            raise

    def _create_openai_provider(self, model: str = None, **kwargs) -> BaseLanguageModel:
        """Create OpenAI LangChain provider"""
        return ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            model=model or getattr(settings, 'LLM_MODEL', 'gpt-4'),
            temperature=kwargs.get("temperature", getattr(settings, 'LLM_TEMPERATURE', 0.1)),
            max_tokens=kwargs.get("max_tokens", getattr(settings, 'MAX_TOKENS', 4000)),
            timeout=kwargs.get("timeout", 60),
            max_retries=kwargs.get("max_retries", 3)
        )

    def _create_anthropic_provider(self, model: str = None, **kwargs) -> BaseLanguageModel:
        """Create Anthropic LangChain provider with compatibility handling"""
        params = {
            "api_key": settings.ANTHROPIC_API_KEY,
            "model": model or "claude-3-sonnet-20240229",
            "temperature": kwargs.get("temperature", getattr(settings, 'LLM_TEMPERATURE', 0.1)),
        }

        max_tokens = kwargs.get("max_tokens", getattr(settings, 'MAX_TOKENS', 4000))
        # Một số version Anthropic dùng "max_tokens", một số dùng "max_tokens_to_sample"
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
            "google_api_key": settings.GOOGLE_API_KEY,
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
            # fallback nếu version khác
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

        # Một số version Ollama không hỗ trợ timeout
        if "timeout" in kwargs:
            try:
                return Ollama(**params, timeout=kwargs["timeout"])
            except TypeError:
                return Ollama(**params)
        else:
            return Ollama(**params)

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

    def test_provider(self, provider: str, model: str = None) -> Dict[str, Any]:
        """Test a provider with a simple query"""
        try:
            llm = self.get_llm(provider, model)

            test_message = [HumanMessage(content="Hello, please respond with 'Test successful'")]
            start_time = datetime.now()

            response = llm.invoke(test_message)
            end_time = datetime.now()

            return {
                "success": True,
                "provider": provider,
                "model": model,
                "response": response.content if hasattr(response, 'content') else str(response),
                "response_time": (end_time - start_time).total_seconds(),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            return {
                "success": False,
                "provider": provider,
                "model": model,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


# Global LLM manager instance
llm_manager = LLMManager()
