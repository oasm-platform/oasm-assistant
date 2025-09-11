from .llm_manager import LLMManager
from common.config import settings
from .llm_manager import LLMConfig

# Initialize LLM manager with settings
llm_manager = LLMManager(
    configs={
        settings.llm.provider: LLMConfig(
            provider=settings.llm.provider,
            api_key=settings.llm.api_key,
            model_name=settings.llm.model_name,
            temperature=settings.llm.temperature,
            max_tokens=settings.llm.max_tokens,
            timeout=settings.llm.timeout,
            max_retries=settings.llm.max_retries,
            base_url=settings.llm.base_url,
            **settings.llm.extra_params
        )
    }
)

__all__ = ['llm_manager']