from .postgres_database import PostgresDatabase
from common.config import settings

pg = PostgresDatabase(settings.postgres.url)

__doc__ = "Postgres database connection"

__all__ = ["pg"]