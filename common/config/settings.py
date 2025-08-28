"""
Global settings & environment variables
"""
from typing import List, Optional
from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class DatabaseSettings(BaseSettings):
    """Database configuration"""
    host: str = Field(default="localhost", env="DB_HOST")
    port: int = Field(default=5432, env="DB_PORT")
    database: str = Field(default="oasm_assistant", env="DB_NAME")
    username: str = Field(default="postgres", env="DB_USER")
    password: str = Field(default="postgres", env="DB_PASSWORD")
    
    @property
    def url(self) -> str:
        return f"postgresql+asyncpg://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    @property
    def sync_url(self) -> str:
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


class LLMSettings(BaseSettings):
    """LLM provider configurations"""
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    google_api_key: Optional[str] = Field(default=None, env="GOOGLE_API_KEY")
    mistral_api_key: Optional[str] = Field(default=None, env="MISTRAL_API_KEY")
    
    default_model: str = Field(default="gpt-3.5-turbo", env="DEFAULT_MODEL")
    max_tokens: int = Field(default=2048, env="MAX_TOKENS")
    temperature: float = Field(default=0.1, env="TEMPERATURE")


class VectorDBSettings(BaseSettings):
    """Vector database configurations"""
    provider: str = Field(default="chroma", env="VECTOR_DB_PROVIDER")
    chroma_host: str = Field(default="localhost", env="CHROMA_HOST")
    chroma_port: int = Field(default=8000, env="CHROMA_PORT")
    qdrant_host: str = Field(default="localhost", env="QDRANT_HOST")
    qdrant_port: int = Field(default=6333, env="QDRANT_PORT")
    
    @property
    def chroma_url(self) -> str:
        return f"http://{self.chroma_host}:{self.chroma_port}"
    
    @property
    def qdrant_url(self) -> str:
        return f"http://{self.qdrant_host}:{self.qdrant_port}"


class SecurityToolSettings(BaseSettings):
    """Security tools configurations"""
    nuclei_templates_path: str = Field(
        default="./knowledge/documents/nuclei_templates", 
        env="NUCLEI_TEMPLATES_PATH"
    )
    nmap_path: str = Field(default="nmap", env="NMAP_PATH")
    subfinder_path: str = Field(default="subfinder", env="SUBFINDER_PATH")
    httpx_path: str = Field(default="httpx", env="HTTPX_PATH")


class Settings(BaseSettings):
    """Global application settings"""
    app_name: str = "OASM Assistant"
    debug: bool = Field(default=False, env="DEBUG")
    environment: str = Field(default="development", env="ENVIRONMENT")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # API Configuration
    api_prefix: str = "/api/v1"
    cors_origins: List[str] = ["*"]
    
    # Security
    secret_key: str = Field(default="your-secret-key-here", env="SECRET_KEY")
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    
    # Sub-configurations
    database: DatabaseSettings = DatabaseSettings()
    llm: LLMSettings = LLMSettings()
    vector_db: VectorDBSettings = VectorDBSettings()
    security_tools: SecurityToolSettings = SecurityToolSettings()
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore"
    )
    
    @field_validator("cors_origins", mode="before")
    def assemble_cors_origins(cls, v):
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        return ["*"]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Global settings instance
settings = get_settings()
