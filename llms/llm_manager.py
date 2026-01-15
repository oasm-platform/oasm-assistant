from typing import Optional, Any, List, Dict
from uuid import UUID
from langchain_core.language_models import BaseLanguageModel
from common.logger import logger
from common.config import configs
from .llm_factory import LLMFactory
from data.database import postgres_db
from data.database.models import LLMConfig
from contextlib import nullcontext


class LLMManager:
    """LLM Manager that provides LLM instances with support for BYOK and default configuration."""

    @staticmethod
    def get_llm(
        workspace_id: Optional[Any] = None,
        user_id: Optional[Any] = None,
        llm_config: Optional[Dict[str, Any]] = None,
        db_session: Optional[Any] = None,
        # Explicit overrides
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
        base_url: Optional[str] = None,
    ) -> BaseLanguageModel:
        """Get an LLM instance with internal resolution logic."""
        
        # 1. Resolve configuration (provider, model, api_key)
        resolved = LLMManager.resolve_llm_config(
            workspace_id=workspace_id,
            user_id=user_id,
            llm_config=llm_config,
            db_session=db_session,
            provider=provider,
            model=model,
            api_key=api_key
        )

        # 2. Resolve parameters (Explicit > llm_config > None/Default)
        def get_p(name, explicit_val):
            if explicit_val is not None:
                return explicit_val
            if llm_config:
                return llm_config.get(name)
            return None

        return LLMFactory.create_llm(
            provider=resolved.get("provider"),
            api_key=resolved.get("api_key"),
            model=resolved.get("model"),
            temperature=get_p("temperature", temperature),
            max_tokens=get_p("max_tokens", max_tokens),
            timeout=get_p("timeout", timeout),
            max_retries=get_p("max_retries", max_retries),
            base_url=get_p("base_url", base_url) or resolved.get("base_url"),
            default_config=configs.llm
        )

    @staticmethod
    def resolve_llm_config(
        workspace_id: Optional[Any] = None,
        user_id: Optional[Any] = None,
        llm_config: Optional[Dict[str, Any]] = None,
        db_session: Optional[Any] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Resolves the LLM configuration to use.
        Priority: 
        1. Explicitly provided arguments (provider, api_key)
        2. Provided llm_config dictionary
        3. Preferred config from database for workspace/user
        4. System default from configs.llm
        """
        # 1. Use explicit if provided
        # For local providers, we don't strictly require api_key
        is_local = LLMManager.is_local_provider(provider)
        if provider and (api_key or is_local):
            return {
                "provider": provider,
                "model": model,
                "api_key": api_key or "EMPTY",
                # Explicit args don't usually include base_url here, handled by caller or llm_config
            }
            
        # 2. Use llm_config if provided
        cfg_provider = llm_config.get("provider") if llm_config else None
        cfg_api_key = llm_config.get("api_key") if llm_config else None
        cfg_is_local = LLMManager.is_local_provider(cfg_provider)
        
        if cfg_provider and (cfg_api_key or cfg_is_local):
            return {
                "provider": cfg_provider,
                "model": llm_config.get("model"),
                "api_key": cfg_api_key or "EMPTY",
                "base_url": llm_config.get("api_url") or llm_config.get("base_url")
            }

        # 3. Try DB-based config
        if workspace_id and user_id:
            try:
                # Use provided session or create a new one
                session_cm = nullcontext(db_session) if db_session and hasattr(db_session, 'query') else postgres_db.get_session()
                
                with session_cm as s:
                    config_obj = s.query(LLMConfig).filter(
                        LLMConfig.workspace_id == workspace_id,
                        LLMConfig.user_id == user_id,
                        LLMConfig.is_preferred == True
                    ).first()
                    
                    if config_obj:
                        logger.debug("✓ Using preferred LLM config: {}/{} for user {}", config_obj.provider, config_obj.model, user_id)
                        return {
                            "provider": config_obj.provider,
                            "model": config_obj.model,
                            "api_key": config_obj.api_key,
                            "base_url": config_obj.api_url
                        }
            except Exception as e:
                logger.error("Error fetching preferred LLM config from DB: {}", e)

        # 4. Fallback to System Default
        default = configs.llm
        return {
            "provider": provider or cfg_provider or default.provider,
            "model": model or (llm_config.get("model") if llm_config else None) or default.model_name,
            "api_key": api_key or cfg_api_key or default.api_key,
            "base_url": (llm_config.get("api_url") if llm_config else None) or (llm_config.get("base_url") if llm_config else None) or default.base_url
        }

    @staticmethod
    def get_friendly_error_message(e: Exception) -> str:
        """Categorize error and return a user-friendly message"""
        error_str = str(e).lower()
        
        # Anthropic Errors
        if "authentication_error" in error_str or "invalid x-api-key" in error_str:
            return "Invalid API key. Please check your LLM configuration settings."
        elif "rate_limit_error" in error_str:
            return "Rate limit exceeded for the selected LLM provider. Please try again later."
        elif "overloaded_error" in error_str:
            return "The LLM provider is currently overloaded. Please try again in a few moments."
        
        # OpenAI Errors
        elif "invalid_api_key" in error_str:
            return "Invalid OpenAI API key. Please check your configuration."
        elif "insufficient_quota" in error_str:
            return "Your LLM provider quota has been exceeded. Please check your billing/limits."
        
        # Google Errors
        elif "api_key_invalid" in error_str or "403" in error_str:
             return "Invalid Google AI API key or service restricted."

        # General gRPC/Network Errors
        if "deadline_exceeded" in error_str:
            return "The request timed out. The LLM provider might be slow or unresponsive."
        elif "unavailable" in error_str:
            return "The LLM service is temporarily unavailable. Please try again later."

        return f"An error occurred while communicated with the AI Service: {str(e)}"

    @staticmethod
    def get_available_providers() -> list[str]:
        """Get list of supported providers"""
        return list(LLMFactory.SUPPORTED_PROVIDERS.keys())

    @staticmethod
    def is_local_provider(provider: str) -> bool:
        """Check if provider is local (doesn't require API key)"""
        return provider in LLMFactory.LOCAL_PROVIDERS