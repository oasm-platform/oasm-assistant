from typing import Optional, Any, List, Dict
from uuid import UUID
from langchain_core.language_models import BaseLanguageModel
from common.logger import logger
from common.config import configs
from .llm_factory import LLMFactory
from data.database import postgres_db
from data.database.models import LLMConfig
from contextlib import nullcontext
from uuid import UUID


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
    async def resolve_llm_config_async(
        workspace_id: Optional[Any] = None,
        user_id: Optional[Any] = None,
        llm_config: Optional[Dict[str, Any]] = None,
        db_session: Optional[Any] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Resolves the LLM configuration asynchronously (DB-aware).
        """
        # 1. Use explicit if provided
        is_local = LLMManager.is_local_provider(provider)
        if provider and (api_key or is_local):
            return {
                "provider": provider,
                "model": model,
                "api_key": api_key or "EMPTY",
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

        # 3. Try DB-based config (Async)
        if workspace_id and user_id:
            try:
                db_workspace_id = UUID(str(workspace_id))
                db_user_id = UUID(str(user_id))
                
                from sqlalchemy import select, desc
                async with postgres_db.get_session() as session:
                    # First try preferred
                    result = await session.execute(select(LLMConfig).filter(
                        LLMConfig.workspace_id == db_workspace_id,
                        LLMConfig.user_id == db_user_id,
                        LLMConfig.is_preferred == True
                    ))
                    config_obj = result.scalars().first()
                    
                    # If no preferred, it will skip and fallback to System Default below
                    if not config_obj:
                         pass

                    if config_obj:
                        logger.debug("✓ Using LLM config: {}/{} for user {}", config_obj.provider, config_obj.model, user_id)
                        return {
                            "provider": config_obj.provider,
                            "model": config_obj.model,
                            "api_key": config_obj.api_key,
                            "base_url": config_obj.api_url
                        }
            except Exception as e:
                logger.error("Error fetching LLM config from DB: {}", e)

        # 4. Fallback to System Default
        default = configs.llm
        return {
            "provider": provider or cfg_provider or default.provider,
            "model": model or (llm_config.get("model") if llm_config else None) or default.model_name,
            "api_key": api_key or cfg_api_key or default.api_key,
            "base_url": ((llm_config.get("api_url") or llm_config.get("base_url")) if llm_config else None) or default.base_url
        }

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
        Resolves the LLM configuration to use (Sync).
        NOTE: Does NOT support DB resolution anymore as DB is async.
        """
        # 1. Use explicit if provided
        is_local = LLMManager.is_local_provider(provider)
        if provider and (api_key or is_local):
            return {
                "provider": provider,
                "model": model,
                "api_key": api_key or "EMPTY",
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

        # 3. DB Attempt - FAIL
        if workspace_id and user_id:
             # We cannot resolve from DB synchronously.
             pass 

        # 4. Fallback to System Default
        default = configs.llm
        return {
            "provider": provider or cfg_provider or default.provider,
            "model": model or (llm_config.get("model") if llm_config else None) or default.model_name,
            "api_key": api_key or cfg_api_key or default.api_key,
            "base_url": ((llm_config.get("api_url") or llm_config.get("base_url")) if llm_config else None) or default.base_url
        }

    @staticmethod
    def get_friendly_error_message(e: Exception) -> str:
        """Categorize error and return a user-friendly message"""
        error_str = str(e).lower()
        
        # Missing Provider or API Key
        if "provider '' not supported" in error_str or "provider 'none' not supported" in error_str:
            return "No LLM provider selected. Please go to Settings -> LLM Manager and select (star) a preferred provider, or ensure a system default is configured."
        
        if "requires api key but none provided" in error_str:
            return "The selected LLM provider requires an API key. Please update your configuration in Settings."

        # Authentication Errors (API Key Invalid)
        if any(sig in error_str for sig in ["invalid_api_key", "authentication_error", "unauthorized", "invalid x-api-key", "401", "forbidden", "403"]):
            return "Authentication failed: Your API key is incorrect, expired, or no longer valid. Please check and update your API key in Settings."

        # Quota/Billing Errors
        if any(sig in error_str for sig in ["insufficient_quota", "billing_not_active", "402", "quota exceeded", "credit"]):
            return "Your LLM provider quota has been exceeded or billing is not active. Please check your provider account and billing settings."

        # Rate Limit Errors
        if any(sig in error_str for sig in ["rate_limit", "too many requests", "429"]):
            return "Rate limit exceeded for the selected LLM provider. Please try again later or increase your request limits."

        # Model Errors
        if any(sig in error_str for sig in ["model_not_found", "invalid model", "404", "does not exist"]):
            return "The selected model is not found or not accessible with your current configuration. Please verify the model name in Settings."

        # Network/Timeout Errors
        if any(sig in error_str for sig in ["deadline_exceeded", "timeout", "timed out", "504", "time out"]):
            return "The request to the AI Service timed out. The provider might be overloaded. Please try again later."
        
        if any(sig in error_str for sig in ["unavailable", "connection failed", "failed to connect", "service_unavailable", "503", "502", "bad gateway", "unreachable"]):
            return "The AI Service is currently unavailable. Please check your API URL configuration and try again later."

        # Configuration/Validation Errors
        if any(sig in error_str for sig in ["invalid", "configuration", "config", "validation", "malformed", "bad request", "400"]):
            return "Configuration error: Please verify your LLM provider settings and API URL are correct."

        # Default: Generic error without provider details
        return "Unable to connect to the LLM provider. Please verify your settings and try again."

    @staticmethod
    def get_available_providers() -> list[str]:
        """Get list of supported providers"""
        return list(LLMFactory.SUPPORTED_PROVIDERS.keys())

    @staticmethod
    def is_local_provider(provider: str) -> bool:
        """Check if provider is local (doesn't require API key)"""
        return provider in LLMFactory.LOCAL_PROVIDERS