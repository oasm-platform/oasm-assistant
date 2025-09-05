from .postgres_database import PostgresDatabase
from common.config import settings
from .chroma_database import ChromaDatabase

pg = PostgresDatabase(settings.postgres.url)
chroma = ChromaDatabase(host=settings.chroma.host, port=settings.chroma.port, persist_directory=settings.chroma.persist_directory)


__all__ = ["pg", "chroma"]