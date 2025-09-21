from .database import PostgresDatabase
from common.config import settings

db = PostgresDatabase(settings.postgres.url)

__all__ = ["db"]