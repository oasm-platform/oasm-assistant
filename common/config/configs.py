from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Dict, Any, Optional
import os


class PostgresConfigs(BaseSettings):
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


class RedisConfigs(BaseSettings):
    url: str = Field("redis://:password@localhost:6379/1", alias="REDIS_URL")
    max_connections: int = Field(10, alias="REDIS_MAX_CONNECTIONS")
    socket_timeout: int = Field(5, alias="REDIS_SOCKET_TIMEOUT")
    socket_connect_timeout: int = Field(5, alias="REDIS_SOCKET_CONNECT_TIMEOUT")
    decode_responses: bool = Field(True, alias="REDIS_DECODE_RESPONSES")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class AppConfigs(BaseSettings):
    host: str = Field("0.0.0.0", alias="APP_HOST")
    port: int = Field(8000, alias="APP_PORT")


class LlmConfigs(BaseSettings):
    provider: str = Field("", alias="LLM_PROVIDER")
    api_key: str = Field("", alias="LLM_API_KEY")
    model_name: str = Field("", alias="LLM_MODEL_NAME")
    temperature: float = Field(0.1, alias="LLM_TEMPERATURE")
    max_tokens: int = Field(4096, alias="LLM_MAX_TOKENS")
    timeout: int = Field(60, alias="LLM_TIMEOUT")
    max_retries: int = Field(3, alias="LLM_MAX_RETRIES")
    base_url: str = Field("", alias="LLM_BASE_URL")
    extra_params: Dict[str, Any] = Field({}, alias="LLM_EXTRA_PARAMS")
    min_chunk_size: int = Field(5, alias="LLM_MIN_CHUNK_SIZE")  # Minimum characters before sending chunk

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  


class EmbeddingConfigs(BaseSettings):
    provider: str = Field("", alias="EMBEDDING_PROVIDER")
    api_key: str = Field("", alias="EMBEDDING_API_KEY")
    model_name: str = Field("", alias="EMBEDDING_MODEL_NAME")
    dimensions: Optional[int] = Field(None, alias="EMBEDDING_DIMENSIONS")
    token_limit: Optional[int] = Field(8192, alias="EMBEDDING_TOKEN_LIMIT")
    org_id: str = Field("", alias="EMBEDDING_ORG_ID")
    base_url: str = Field("", alias="EMBEDDING_BASE_URL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

class SchedulerConfigs(BaseSettings):
    """Scheduler configurations for periodic tasks"""
    nuclei_templates_sync_time: str = Field("0 0 * * *", alias="NUCLEI_TEMPLATES_SYNC_TIME")
    nuclei_templates_repo_url: str = Field(
        "https://github.com/projectdiscovery/nuclei-templates.git",
        alias="NUCLEI_TEMPLATES_REPO_URL"
    )
    nuclei_templates_clone_dir: str = Field(
        "C:\\nuclei-templates" if os.name == 'nt' else "/tmp/nuclei-templates",
        alias="NUCLEI_TEMPLATES_CLONE_DIR"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class RAGConfigs(BaseSettings):
    """RAG (Retrieval-Augmented Generation) configurations for template search"""
    # Hybrid search weights
    vector_weight: float = Field(0.7, alias="RAG_VECTOR_WEIGHT")
    keyword_weight: float = Field(0.3, alias="RAG_KEYWORD_WEIGHT")

    # Search parameters
    top_k: int = Field(3, alias="RAG_TOP_K")
    candidates_multiplier: int = Field(3, alias="RAG_CANDIDATES_MULTIPLIER")
    max_candidates: int = Field(15, alias="RAG_MAX_CANDIDATES")
    vector_k: int = Field(50, alias="RAG_VECTOR_K")
    keyword_k: int = Field(50, alias="RAG_KEYWORD_K")

    # Quality thresholds
    similarity_threshold: float = Field(0.55, alias="RAG_SIMILARITY_THRESHOLD")
    min_score: float = Field(0.0, alias="RAG_MIN_SCORE")

    # Database table
    table_name: str = Field("nuclei_templates", alias="RAG_TABLE_NAME")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

class DomainClassifierConfigs(BaseSettings):
    min_labels: int = Field(3, alias="DOMAIN_CLASSIFIER_MIN_LABELS")
    max_labels: int = Field(5, alias="DOMAIN_CLASSIFIER_MAX_LABELS")
    max_retries: int = Field(3, alias="DOMAIN_CLASSIFIER_MAX_RETRIES")
    categories: list[str] = Field(
        default=[
            "E-Commerce", "News", "Blog", "Social Media", "Education",
            "Business", "Technology", "Health", "Entertainment", "Sports",
            "Finance", "Government", "Nonprofit", "Personal", "Forum",
            "Documentation", "Portfolio", "Landing Page", "Adult",
            "Travel", "Food", "Gaming", "Music", "Art", "Photography",
            "Fashion", "Automotive", "Real Estate", "Job Portal", "Dating",
            "Streaming", "Podcast", "Wiki", "Search Engine", "Cloud Service",
            "API", "Marketplace", "Cryptocurrency", "Banking", "Insurance",
            "Legal", "Consulting", "Marketing", "Design", "Startup",
            "Agency", "SaaS", "Tools", "Utilities", "Weather"
        ],
        alias="DOMAIN_CLASSIFIER_CATEGORIES"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

class MemoryConfigs(BaseSettings):
    # Short-Term Memory (STM) Settings (1 Message Unit = 1 Question + 1 Answer)
    stm_summary_stack_messages: int = Field(4, alias="MEMORY_STM_SUMMARY_STACK_MESSAGES")
    stm_context_messages: int = Field(3, alias="MEMORY_STM_CONTEXT_MESSAGES")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

class NucleiGenerateConfigs(BaseSettings):
    """Nuclei Generator Agent configurations"""
    rag_limit: int = Field(3, alias="NUCLEI_RAG_LIMIT")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

class Configs(BaseSettings):
    postgres: PostgresConfigs = PostgresConfigs()
    redis: RedisConfigs = RedisConfigs()
    app: AppConfigs = AppConfigs()
    llm: LlmConfigs = LlmConfigs()
    embedding: EmbeddingConfigs = EmbeddingConfigs()
    scheduler: SchedulerConfigs = SchedulerConfigs()
    rag: RAGConfigs = RAGConfigs()
    domain_classifier: DomainClassifierConfigs = DomainClassifierConfigs()
    memory: MemoryConfigs = MemoryConfigs()
    nuclei: NucleiGenerateConfigs = NucleiGenerateConfigs()

    # Add missing fields used in main.py
    host: str = Field("0.0.0.0", alias="HOST")
    port: int = Field(8000, alias="PORT")
    max_workers: int = Field(10, alias="MAX_WORKERS")
    service_name: str = Field("oasm-assistant", alias="SERVICE_NAME")
    version: str = Field("1.0.0", alias="VERSION")
    oasm_cloud_apikey: str = Field("change_me", alias="OASM_CLOUD_APIKEY")
    oasm_core_api_url: str = Field("http://localhost:6276", alias="OASM_CORE_API_URL")
    searxng_url: str = Field("http://localhost:8080", alias="SEARXNG_URL")

    # Add missing fields used in domain_classifier.py
    crawl_timeout: int = Field(10, alias="CRAWL_TIMEOUT")
    crawl_max_retries: int = Field(3, alias="CRAWL_MAX_RETRIES")
    classification_confidence_threshold: float = Field(0.3, alias="CLASSIFICATION_CONFIDENCE_THRESHOLD")

    # MCP service timeout
    mcp_timeout: int = Field(30, alias="MCP_TIMEOUT")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
