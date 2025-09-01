from pydantic import Field
from pydantic_settings import BaseSettings


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


class AppSettings(BaseSettings):
    host: str = Field("0.0.0.0", alias="APP_HOST")
    port: int = Field(8000, alias="APP_PORT")


class Settings(BaseSettings):
    postgres: PostgresSettings = PostgresSettings()
    chroma: ChromaSettings = ChromaSettings()
    app: AppSettings = AppSettings()

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
