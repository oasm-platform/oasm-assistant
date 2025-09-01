import time
from typing import Optional

from sqlmodel import create_engine, Session
from sqlalchemy import text
from sqlalchemy.exc import OperationalError


class PostgresDatabase:
    def __init__(
        self,
        url: str,
        echo: bool = False,
        pool_size: int = 5, 
        max_overflow: int = 10,
        pool_timeout: int = 30,
        pool_recycle: int = 1800,
        retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self.engine = create_engine(
            url,
            echo=echo,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_recycle=pool_recycle,
        )
        self.retries = retries
        self.retry_delay = retry_delay

    def _run_with_retry(self, func, *args, **kwargs):
        last_exception = None
        for attempt in range(1, self.retries + 1):
            try:
                return func(*args, **kwargs)
            except OperationalError as e:
                last_exception = e
                print(f"[DB] OperationalError, retry {attempt}/{self.retries}...")
                time.sleep(self.retry_delay)
        raise last_exception

    def execute(self, sql: str, params: Optional[dict] = None):
        """Execute SELECT many rows"""
        def _exec():
            with Session(self.engine) as session:
                result = session.exec(text(sql), params or {})
                return result.fetchall()

        return self._run_with_retry(_exec)

    def execute_one(self, sql: str, params: Optional[dict] = None):
        """Execute SELECT one row"""
        def _exec():
            with Session(self.engine) as session:
                result = session.exec(text(sql), params or {})
                return result.first()

        return self._run_with_retry(_exec)

    def execute_commit(self, sql: str, params: Optional[dict] = None):
        """Execute INSERT/UPDATE/DELETE"""
        def _exec():
            with Session(self.engine) as session:
                session.exec(text(sql), params or {})
                session.commit()

        return self._run_with_retry(_exec)

    def __enter__(self):
        """Use with PostgresDatabase(...) as db"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close connection pool"""
        self.engine.dispose() 
