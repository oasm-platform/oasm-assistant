from typing import Optional, Any, List, Dict
from uuid import UUID
from langchain_core.language_models import BaseLanguageModel
from common.logger import logger
from common.config import configs
from .llm_factory import LLMFactory
from data.database import postgres_db


class LLMManager:
    """LLM Manager that provides LLM instances with support for BYOK and default configuration."""

    @staticmethod
    def get_llm(
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        db_session: Optional[Any] = None,
        workspace_id: Optional[Any] = None,
        user_id: Optional[Any] = None,
        **kwargs
    ) -> BaseLanguageModel:
        """Get an LLM instance."""
        
        # 1. Resolve configuration
        config = LLMManager.resolve_llm_config(
            provider=provider,
            model=model,
            api_key=api_key,
            workspace_id=workspace_id,
            user_id=user_id,
            db_session=db_session
        )

        # 2. Use LLMFactory to create the instance
        return LLMFactory.create_llm(
            provider=config.get("provider"),
            api_key=config.get("api_key"),
            model=config.get("model"),
            default_config=configs.llm,
            **kwargs
        )

    @staticmethod
    def resolve_llm_config(
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        workspace_id: Optional[Any] = None,
        user_id: Optional[Any] = None,
        db_session: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Resolves the LLM configuration to use.
        Priority: 
        1. Explicitly provided provider/api_key/model
        2. Preferred config from database for workspace/user
        3. System default from configs.llm
        """
        # 1. Use explicit if provided
        if provider and api_key:
            return {
                "provider": provider,
                "model": model,
                "api_key": api_key
            }

        # 2. Try DB-based config
        if workspace_id and user_id:
            try:
                from data.database.models import LLMConfig
                
                def _get_query(s):
                    return s.query(LLMConfig).filter(
                        LLMConfig.workspace_id == workspace_id,
                        LLMConfig.user_id == user_id,
                        LLMConfig.is_preferred == True
                    )

                config_data = None
                # Check if we have a valid session object with .query() method
                if db_session and hasattr(db_session, 'query'):
                    config_obj = _get_query(db_session).first()
                    if config_obj:
                        config_data = {
                            "provider": config_obj.provider,
                            "model": config_obj.model,
                            "api_key": config_obj.api_key
                        }
                else:
                    # Otherwise open a new session and extract data immediately
                    with postgres_db.get_session() as s:
                        config_obj = _get_query(s).first()
                        if config_obj:
                            config_data = {
                                "provider": config_obj.provider,
                                "model": config_obj.model,
                                "api_key": config_obj.api_key
                            }

                if config_data:
                    logger.debug(f"✓ Using preferred LLM config: {config_data['provider']}/{config_data['model']} for user {user_id}")
                    return config_data
            except Exception as e:
                logger.error("Error fetching preferred LLM config from DB: {}", e)

        # 3. Fallback to System Default
        default = configs.llm
        return {
            "provider": provider or default.provider,
            "model": model or default.model_name,
            "api_key": api_key or default.api_key
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