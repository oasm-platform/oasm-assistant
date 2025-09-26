from .llm_manager import LLMManager
from common.config import configs
from common.config import LlmConfigs

# Initialize LLM manager with settings
llm_manager = LLMManager(
    config=LlmConfigs(
            provider=configs.llm.provider,
            api_key=configs.llm.api_key,
            model_name=configs.llm.model_name,
            temperature=configs.llm.temperature,
            max_tokens=configs.llm.max_tokens,
            timeout=configs.llm.timeout,
            max_retries=configs.llm.max_retries,
            base_url=configs.llm.base_url,
            **configs.llm.extra_params
        )
)

__all__ = ['llm_manager', 'LLMManager']