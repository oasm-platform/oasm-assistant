from .database import PostgresDatabase
from common.config import configs as settings

postgres_db = PostgresDatabase(settings.postgres.url)

__all__ = ["postgres_db", "PostgresDatabase"]
