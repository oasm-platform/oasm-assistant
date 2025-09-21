from .postgres_database import PostgresDatabase
from common.config import settings

pg = PostgresDatabase(settings.postgres.url)

__all__ = ["pg"]