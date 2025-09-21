from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Dict, List, Any, Optional


class PostgresSettings(BaseSettings):
    host: str = Field("localhost", alias="POSTGRES_HOST")
    port: int = Field(5432, alias="POSTGRES_PORT")
    user: str = Field("postgres", alias="POSTGRES_USER")
    password: str = Field("postgres", alias="POSTGRES_PASSWORD")
    database: str = Field("open_asm", alias="POSTGRES_DB")

    @property
    def url(self) -> str:
        """Create connection URL"""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  


class AppSettings(BaseSettings):
    host: str = Field("0.0.0.0", alias="APP_HOST")
    port: int = Field(8000, alias="APP_PORT")


class LlmSettings(BaseSettings):
    provider: str = Field("", alias="LLM_PROVIDER")
    api_key: str = Field("", alias="LLM_API_KEY")
    model_name: str = Field("", alias="LLM_MODEL_NAME")
    temperature: float = Field(0.1, alias="LLM_TEMPERATURE")
    max_tokens: int = Field(4000, alias="LLM_MAX_TOKENS")
    timeout: int = Field(60, alias="LLM_TIMEOUT")
    max_retries: int = Field(3, alias="LLM_MAX_RETRIES")
    base_url: str = Field("", alias="LLM_BASE_URL")
    extra_params: Dict[str, Any] = Field({}, alias="LLM_EXTRA_PARAMS")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  


class EmbeddingSettings(BaseSettings):
    provider: str = Field("", alias="EMBEDDING_PROVIDER")
    api_key: str = Field("", alias="EMBEDDING_API_KEY")
    model_name: str = Field("", alias="EMBEDDING_MODEL_NAME")
    dimensions: Optional[int] = Field(None, alias="EMBEDDING_DIMENSIONS")
    token_limit: int = Field(8192, alias="EMBEDDING_TOKEN_LIMIT")
    org_id: str = Field("", alias="EMBEDDING_ORG_ID")
    base_url: str = Field("", alias="EMBEDDING_BASE_URL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

class WebSearchSettings(BaseSettings):
    default_search_engines_str: str = Field("duckduckgo", alias="DEFAULT_SEARCH_ENGINES")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  
    
    @property
    def default_search_engines(self) -> List[str]:
        """Parse the default_search_engines string into a list"""
        raw_val = self.default_search_engines_str
        if raw_val:
            # Check if it's a JSON array
            if raw_val.startswith('[') and raw_val.endswith(']'):
                import json
                try:
                    return json.loads(raw_val)
                except Exception:
                    # If JSON parsing fails, fall back to comma-separated
                    return [engine.strip() for engine in raw_val.strip('[]').split(',') if engine.strip()] or ["duckduckgo"]
            else:
                # Handle comma-separated string
                return [engine.strip() for engine in raw_val.split(',')] if raw_val else ["duckduckgo"]
        else:
            # Default fallback
            return ["duckduckgo"]
    
    # DuckDuckGo settings
    duckduckgo_timeout: int = Field(10, alias="DUCKDUCKGO_TIMEOUT")
    duckduckgo_max_results: int = Field(10, alias="DUCKDUCKGO_MAX_RESULTS")
    
    # Google Search settings
    google_search_api_key: str = Field("", alias="GOOGLE_SEARCH_API_KEY")
    google_search_engine_id: str = Field("", alias="GOOGLE_SEARCH_ENGINE_ID")
    google_max_results: int = Field(10, alias="GOOGLE_MAX_RESULTS")
    
    # Bing Search settings
    bing_search_api_key: str = Field("", alias="BING_SEARCH_API_KEY")
    bing_timeout: int = Field(10, alias="BING_TIMEOUT")
    bing_max_results: int = Field(10, alias="BING_MAX_RESULTS")
    
    # Tavily Search settings
    tavily_api_key: str = Field("", alias="TAVILY_API_KEY")
    tavily_timeout: int = Field(10, alias="TAVILY_TIMEOUT")
    tavily_max_results: int = Field(5, alias="TAVILY_MAX_RESULTS")
    
    # SerpApi settings
    serpapi_api_key: str = Field("", alias="SERPAPI_API_KEY")
    serpapi_timeout: int = Field(10, alias="SERPAPI_TIMEOUT")
    serpapi_max_results: int = Field(10, alias="SERPAPI_MAX_RESULTS")
    
    # General settings
    max_results_per_engine: int = Field(5, alias="MAX_RESULTS_PER_ENGINE")
    validate_search_sources: bool = Field(True, alias="VALIDATE_SEARCH_SOURCES")


class Settings(BaseSettings):
    postgres: PostgresSettings = PostgresSettings()
    app: AppSettings = AppSettings()
    web_search: WebSearchSettings = WebSearchSettings()
    llm: LlmSettings = LlmSettings()
    embedding: EmbeddingSettings = EmbeddingSettings()
    
    # Add missing fields used in main.py
    host: str = Field("0.0.0.0", alias="HOST")
    port: int = Field(8000, alias="PORT")
    max_workers: int = Field(10, alias="MAX_WORKERS")
    service_name: str = Field("oasm-assistant", alias="SERVICE_NAME")
    version: str = Field("1.0.0", alias="VERSION")
    
    # Add missing fields used in domain_classifier.py
    crawl_timeout: int = Field(10, alias="CRAWL_TIMEOUT")
    crawl_max_retries: int = Field(3, alias="CRAWL_MAX_RETRIES")
    classification_confidence_threshold: float = Field(0.3, alias="CLASSIFICATION_CONFIDENCE_THRESHOLD")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

