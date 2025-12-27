from typing import Optional
from langchain_core.language_models import BaseLanguageModel
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from common.config import LlmConfigs
from common.config.constants import OASM_MODELS


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
        default_config: Optional[LlmConfigs] = None,
        **kwargs
    ) -> BaseLanguageModel:
        """Create an LLM instance based on provider and configuration."""
        # Auto-detect if it's an OASM system model
        if model:
            is_oasm = any(m["name"] == model or m["id"] == model for m in OASM_MODELS)
            if is_oasm:
                provider = "oasm"

        if provider not in LLMFactory.SUPPORTED_PROVIDERS:
            available = list(LLMFactory.SUPPORTED_PROVIDERS.keys())
            raise ValueError(
                f"Provider '{provider}' not supported. Available: {available}"
            )

        if provider not in LLMFactory.LOCAL_PROVIDERS and not api_key:
            if not default_config or not default_config.api_key:
                raise ValueError(
                    f"Provider '{provider}' requires API key but none provided"
                )
            api_key = default_config.api_key

        factory_method_name = LLMFactory.SUPPORTED_PROVIDERS[provider]
        factory_method = getattr(LLMFactory, factory_method_name)

        return factory_method(
            api_key=api_key,
            model=model,
            default_config=default_config,
            **kwargs
        )

    @staticmethod
    def _create_openai_provider(
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        default_config: Optional[LlmConfigs] = None,
        **kwargs
    ) -> BaseLanguageModel:
        """Create OpenAI LangChain provider"""
        if not api_key:
            raise ValueError("OpenAI requires API key")

        model_name = model or (default_config.model_name if default_config else "gpt-3.5-turbo")
        temperature = kwargs.get("temperature", default_config.temperature if default_config else 0.1)
        max_tokens = kwargs.get("max_tokens", default_config.max_tokens if default_config else 2048)
        timeout = kwargs.get("timeout", default_config.timeout if default_config else 60)
        max_retries = kwargs.get("max_retries", default_config.max_retries if default_config else 2)
        extra_params = default_config.extra_params if default_config else {}

        return ChatOpenAI(
            api_key=api_key,
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
            **extra_params
        )

    @staticmethod
    def _create_anthropic_provider(
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        default_config: Optional[LlmConfigs] = None,
        **kwargs
    ) -> BaseLanguageModel:
        """Create Anthropic LangChain provider"""
        if not api_key:
            raise ValueError("Anthropic requires API key")

        model_name = model or (default_config.model_name if default_config else "claude-3-sonnet-20240229")
        temperature = kwargs.get("temperature", default_config.temperature if default_config else 0.1)
        max_tokens = kwargs.get("max_tokens", default_config.max_tokens if default_config else 2048)
        timeout = kwargs.get("timeout", default_config.timeout if default_config else 60)
        max_retries = kwargs.get("max_retries", default_config.max_retries if default_config else 2)
        extra_params = default_config.extra_params if default_config else {}

        params = {
            "api_key": api_key,
            "model": model_name,
            "temperature": temperature,
            **extra_params
        }

        try:
            return ChatAnthropic(
                **params,
                max_tokens=max_tokens,
                timeout=timeout,
                max_retries=max_retries
            )
        except TypeError:
            return ChatAnthropic(
                **params,
                max_tokens_to_sample=max_tokens,
                timeout=timeout,
                max_retries=max_retries
            )

    @staticmethod
    def _create_google_provider(
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        default_config: Optional[LlmConfigs] = None,
        **kwargs
    ) -> BaseLanguageModel:
        """Create Google LangChain provider"""
        if not api_key:
            raise ValueError("Google requires API key")

        model_name = model or (default_config.model_name if default_config else "gemini-2.0-flash")
        temperature = kwargs.get("temperature", default_config.temperature if default_config else 0.1)
        max_tokens = kwargs.get("max_tokens", default_config.max_tokens if default_config else 2048)
        timeout = kwargs.get("timeout", 60)
        max_retries = kwargs.get("max_retries", 2)
        extra_params = default_config.extra_params if default_config else {}

        params = {
            "google_api_key": api_key,
            "model": model_name,
            "temperature": temperature,
            **extra_params
        }

        try:
            return ChatGoogleGenerativeAI(
                **params,
                max_output_tokens=max_tokens,
                max_retries=max_retries,
                timeout=timeout
            )
        except TypeError:
            return ChatGoogleGenerativeAI(
                **params,
                max_tokens=max_tokens,
                max_retries=max_retries,
                timeout=timeout
            )

    @staticmethod
    def _create_ollama_provider(
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        default_config: Optional[LlmConfigs] = None,
        **kwargs
    ) -> BaseLanguageModel:
        """Create Ollama LangChain provider"""
        model_name = model or (default_config.model_name if default_config else "llama2")
        temperature = kwargs.get("temperature", default_config.temperature if default_config else 0.1)
        base_url = kwargs.get("base_url", default_config.base_url if default_config else "http://localhost:8005")
        extra_params = default_config.extra_params if default_config else {}

        params = {
            "model": model_name,
            "temperature": temperature,
            "base_url": base_url,
            **extra_params
        }

        if "timeout" in kwargs:
            try:
                return ChatOllama(**params, timeout=kwargs["timeout"])
            except TypeError:
                return ChatOllama(**params)
        else:
            return ChatOllama(**params)

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
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        default_config: Optional[LlmConfigs] = None,
        **kwargs
    ) -> BaseLanguageModel:
        """Create vLLM LangChain provider using OpenAI-compatible API"""
        return LLMFactory._create_openai_compatible_provider(
            provider_name="vllm",
            default_base_url="http://localhost:8006/v1",
            default_model="Qwen/Qwen2.5-7B-Instruct",
            api_key=api_key,
            model=model,
            default_config=default_config,
            **kwargs
        )

    @staticmethod
    def _create_sglang_provider(
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        default_config: Optional[LlmConfigs] = None,
        **kwargs
    ) -> BaseLanguageModel:
        """Create SGLang LangChain provider using OpenAI-compatible API"""
        return LLMFactory._create_openai_compatible_provider(
            provider_name="sglang",
            default_base_url="http://localhost:8007/v1",
            default_model="Qwen/Qwen2.5-7B-Instruct",
            api_key=api_key,
            model=model,
            default_config=default_config,
            **kwargs
        )
    @staticmethod
    def _create_oasm_provider(
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        default_config: Optional[LlmConfigs] = None,
        **kwargs
    ) -> BaseLanguageModel:
        """Create OASM specialized provider (Built-in)"""
        # For OASM provider, we use a system-level key if none provided
        from common.config import configs
        from common.logger import logger
        
        system_key = configs.oasm_cloud_apikey
        
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
                default_config=default_config,
                **kwargs
            )
            
        # Map OASM display name to internal model name
        # Try to find by name or id
        oasm_info = next((m for m in OASM_MODELS if m["name"] == model or m["id"] == model), None)
        model_name = oasm_info["internal_model"] if oasm_info else "gemini-1.5-flash"
        
        return LLMFactory._create_vllm_provider(
            api_key=system_key,
            model=model_name,
            default_config=default_config,
            **kwargs
        )
