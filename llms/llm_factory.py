from typing import Optional
from langchain_core.language_models import BaseLanguageModel
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from common.config import configs, LlmConfigs
from common.config.constants import OASM_MODELS
from common.logger import logger


class LLMFactory:
    """Factory for creating LLM instances based on provider and configuration."""

    SUPPORTED_PROVIDERS = {
        "openai": "_create_openai_provider",
        "anthropic": "_create_anthropic_provider",
        "google": "_create_google_provider",
        "ollama": "_create_ollama_provider",
        "vllm": "_create_vllm_provider",
        "sglang": "_create_sglang_provider",
        "oasm": "_create_oasm_provider",
    }

    LOCAL_PROVIDERS = {"ollama", "vllm", "sglang", "oasm"}

    @staticmethod
    def create_llm(
        provider: str,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
        base_url: Optional[str] = None,
        default_config: Optional[LlmConfigs] = None,
    ) -> BaseLanguageModel:
        """Create an LLM instance based on provider and configuration."""
        
        # Load default config if not provided
        if not default_config:
            default_config = configs.llm

        # Auto-detect if it's an OASM system model
        actual_model = model or default_config.model_name
        if actual_model:
            is_oasm = any(m["name"] == actual_model or m["id"] == actual_model for m in OASM_MODELS)
            if is_oasm:
                provider = "oasm"

        if provider not in LLMFactory.SUPPORTED_PROVIDERS:
            available = list(LLMFactory.SUPPORTED_PROVIDERS.keys())
            raise ValueError(
                f"Provider '{provider}' not supported. Available: {available}"
            )

        # Resolve parameters
        resolved_api_key = api_key or default_config.api_key
        resolved_temperature = temperature if temperature is not None else default_config.temperature
        resolved_max_tokens = max_tokens if max_tokens is not None else default_config.max_tokens
        resolved_timeout = timeout if timeout is not None else default_config.timeout
        resolved_max_retries = max_retries if max_retries is not None else default_config.max_retries
        resolved_base_url = base_url or default_config.base_url

        if provider not in LLMFactory.LOCAL_PROVIDERS and not resolved_api_key:
             raise ValueError(f"Provider '{provider}' requires API key but none provided")

        factory_method_name = LLMFactory.SUPPORTED_PROVIDERS[provider]
        factory_method = getattr(LLMFactory, factory_method_name)

        return factory_method(
            api_key=resolved_api_key,
            model=actual_model,
            temperature=resolved_temperature,
            max_tokens=resolved_max_tokens,
            timeout=resolved_timeout,
            max_retries=resolved_max_retries,
            base_url=resolved_base_url
        )

    @staticmethod
    def _create_openai_provider(
        api_key: str,
        model: str,
        temperature: float,
        max_tokens: int,
        timeout: int,
        max_retries: int,
        base_url: Optional[str] = None
    ) -> BaseLanguageModel:
        """Create OpenAI LangChain provider"""
        return ChatOpenAI(
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
            base_url=base_url
        )

    @staticmethod
    def _create_anthropic_provider(
        api_key: str,
        model: str,
        temperature: float,
        max_tokens: int,
        timeout: int,
        max_retries: int,
        base_url: Optional[str] = None
    ) -> BaseLanguageModel:
        """Create Anthropic LangChain provider"""
        try:
            return ChatAnthropic(
                api_key=api_key,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                max_retries=max_retries,
                base_url=base_url
            )
        except TypeError:
            return ChatAnthropic(
                api_key=api_key,
                model=model,
                temperature=temperature,
                max_tokens_to_sample=max_tokens,
                timeout=timeout,
                max_retries=max_retries,
                base_url=base_url
            )

    @staticmethod
    def _create_google_provider(
        api_key: str,
        model: str,
        temperature: float,
        max_tokens: int,
        timeout: int,
        max_retries: int,
        base_url: Optional[str] = None
    ) -> BaseLanguageModel:
        """Create Google LangChain provider"""
        try:
            return ChatGoogleGenerativeAI(
                google_api_key=api_key,
                model=model,
                temperature=temperature,
                max_output_tokens=max_tokens,
                max_retries=max_retries,
                timeout=timeout,
                base_url=base_url
            )
        except TypeError:
            return ChatGoogleGenerativeAI(
                google_api_key=api_key,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                max_retries=max_retries,
                timeout=timeout,
                base_url=base_url
            )

    @staticmethod
    def _create_ollama_provider(
        api_key: str,
        model: str,
        temperature: float,
        max_tokens: int,
        timeout: int,
        max_retries: int,
        base_url: Optional[str] = None
    ) -> BaseLanguageModel:
        """Create Ollama LangChain provider"""
        return ChatOllama(
            model=model,
            temperature=temperature,
            num_predict=max_tokens,
            base_url=base_url or "http://localhost:8005",
            timeout=timeout,
            max_retries=max_retries
        )

    @staticmethod
    def _create_openai_compatible_provider(
        provider_name: str,
        default_base_url: str,
        default_model: str,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        default_config: Optional[LlmConfigs] = None,
        **kwargs
    ) -> BaseLanguageModel:
        """Create a LangChain provider for an OpenAI-compatible API (vLLM, SGLang)"""
        model_name = model or (default_config.model_name if default_config else default_model)
        temperature = kwargs.get("temperature", default_config.temperature if default_config else 0.1)
        base_url = kwargs.get("base_url", default_config.base_url if default_config else default_base_url)
        max_tokens = kwargs.get("max_tokens", default_config.max_tokens if default_config else 2048)
        timeout = kwargs.get("timeout", default_config.timeout if default_config else 60)
        max_retries = kwargs.get("max_retries", default_config.max_retries if default_config else 2)
        extra_params = default_config.extra_params if default_config else {}

        params = {
            "model": model_name,
            "temperature": temperature,
            "base_url": base_url,
            "api_key": "EMPTY",
            "max_tokens": max_tokens,
            "timeout": timeout,
            "max_retries": max_retries,
            **extra_params
        }

        return ChatOpenAI(**params)

    @staticmethod
    def _create_vllm_provider(
        api_key: str,
        model: str,
        temperature: float,
        max_tokens: int,
        timeout: int,
        max_retries: int,
        base_url: Optional[str] = None
    ) -> BaseLanguageModel:
        """Create vLLM LangChain provider using OpenAI-compatible API"""
        return LLMFactory._create_openai_compatible_provider(
            provider_name="vLLM",
            default_base_url="http://localhost:8006/v1",
            default_model="Qwen/Qwen2.5-7B-Instruct",
            api_key=api_key or "EMPTY",
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
            base_url=base_url
        )

    @staticmethod
    def _create_sglang_provider(
        api_key: str,
        model: str,
        temperature: float,
        max_tokens: int,
        timeout: int,
        max_retries: int,
        base_url: Optional[str] = None
    ) -> BaseLanguageModel:
        """Create SGLang LangChain provider using OpenAI-compatible API"""
        return LLMFactory._create_openai_compatible_provider(
            provider_name="SGLang",
            default_base_url="http://localhost:8007/v1",
            default_model="Qwen/Qwen2.5-7B-Instruct",
            api_key=api_key or "EMPTY",
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
            base_url=base_url
        )

    @staticmethod
    def _create_oasm_provider(
        api_key: str,
        model: str,
        temperature: float,
        max_tokens: int,
        timeout: int,
        max_retries: int,
        base_url: Optional[str] = None
    ) -> BaseLanguageModel:
        """Create OASM specialized provider (Built-in)"""
        system_key = api_key
        
        # If OASM cloud key is not configured, dispatch to the default system LLM (e.g., vLLM)
        if not system_key or system_key == "change_me":
             # Avoid infinite loop if general provider is also 'oasm'
             if configs.llm.provider == "oasm":
                raise ValueError("Infinite loop detected: OASM_CLOUD_APIKEY missing and LLM_PROVIDER is also 'oasm'")
                
             logger.debug(f"OASM_CLOUD_APIKEY not set, dispatching {model} to default provider: {configs.llm.provider}")
             return LLMFactory.create_llm(
                 provider=configs.llm.provider,
                 api_key=configs.llm.api_key,
                 model=configs.llm.model_name,
                 temperature=temperature,
                 max_tokens=max_tokens,
                 timeout=timeout,
                 max_retries=max_retries,
                 base_url=base_url
             )
            
        # Map OASM display name to internal model name
        oasm_info = next((m for m in OASM_MODELS if m["name"] == model or m["id"] == model), None)
        model_name = oasm_info["internal_model"] if oasm_info else "gemini-1.5-flash"
        
        return LLMFactory._create_vllm_provider(
            api_key=system_key,
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
            base_url=base_url
        )
