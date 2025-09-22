from .database import PostgresDatabase
from common.config import configs as settings

db = PostgresDatabase(settings.postgres.url)

__all__ = ["db"]