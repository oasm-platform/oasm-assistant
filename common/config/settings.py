from pydantic import Field
from pydantic_settings import BaseSettings
from typing import List


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


class ChromaSettings(BaseSettings):
    host: str = Field("localhost", alias="CHROMA_HOST")
    port: int = Field(8000, alias="CHROMA_PORT")
    persist_directory: str = Field("", alias="CHROMA_PERSIST_DIRECTORY")


class AppSettings(BaseSettings):
    host: str = Field("0.0.0.0", alias="APP_HOST")
    port: int = Field(8000, alias="APP_PORT")


class LlmSettings(BaseSettings):
    provider: str = Field("", alias="LLM_PROVIDER")
    api_key: str = Field("", alias="LLM_API_KEY")
    model_name: str = Field("", alias="LLM_MODEL_NAME")


class WebSearchSettings(BaseSettings):
    # Default search engines
    default_search_engines: List[str] = Field(["duckduckgo"], alias="DEFAULT_SEARCH_ENGINES")
    
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
    chroma: ChromaSettings = ChromaSettings()
    app: AppSettings = AppSettings()
    web_search: WebSearchSettings = WebSearchSettings()
    llm: LlmSettings = LlmSettings()

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
