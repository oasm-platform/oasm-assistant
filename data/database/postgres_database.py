import time
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import OperationalError


class PostgresDatabase:
    """PostgreSQL database connection manager with raw SQL support"""
    
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
        """
        Initialize PostgreSQL database connection
        
        Args:
            url: Database connection URL
            echo: Whether to log SQL queries
            pool_size: Connection pool size
            max_overflow: Maximum pool overflow
            pool_timeout: Pool timeout in seconds
            pool_recycle: Pool recycle time in seconds
            retries: Number of retry attempts
            retry_delay: Delay between retries in seconds
        """
        self.engine = create_engine(
            url,
            echo=echo,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_recycle=pool_recycle,
        )
        
        # Create session factory instead of single session
        self.SessionFactory = sessionmaker(bind=self.engine)
        
        self.retries = retries
        self.retry_delay = retry_delay

    @contextmanager
    def get_session(self):
        """Get a database session with automatic cleanup"""
        session = self.SessionFactory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def _run_with_retry(self, func, *args, **kwargs):
        """Execute function with retry logic for operational errors"""
        last_exception = None
        for attempt in range(1, self.retries + 1):
            try:
                return func(*args, **kwargs)
            except OperationalError as e:
                last_exception = e
                if attempt < self.retries:
                    time.sleep(self.retry_delay)
                else:
                    raise last_exception

    def select_all(
        self, 
        raw_sql: str, 
        params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute SELECT query and return all results as list of dictionaries
        
        Args:
            raw_sql: Raw SQL query string
            params: Query parameters dictionary
            
        Returns:
            List of dictionaries representing rows
        """
        def _exec():
            with self.get_session() as session:
                result = session.execute(text(raw_sql), params or {})
                # Convert to list of dictionaries
                columns = result.keys()
                return [dict(zip(columns, row)) for row in result.fetchall()]
        
        return self._run_with_retry(_exec)

    def select_one(
        self, 
        raw_sql: str, 
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Execute SELECT query and return first result as dictionary
        
        Args:
            raw_sql: Raw SQL query string
            params: Query parameters dictionary
            
        Returns:
            Dictionary representing the row, or None if not found
        """
        def _exec():
            with self.get_session() as session:
                result = session.execute(text(raw_sql), params or {})
                row = result.fetchone()
                if row:
                    columns = result.keys()
                    return dict(zip(columns, row))
                return None
        
        return self._run_with_retry(_exec)

    def select_scalar(
        self, 
        raw_sql: str, 
        params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Execute SELECT query and return single scalar value
        
        Args:
            raw_sql: Raw SQL query string
            params: Query parameters dictionary
            
        Returns:
            Single scalar value
        """
        def _exec():
            with self.get_session() as session:
                result = session.execute(text(raw_sql), params or {})
                return result.scalar()
        
        return self._run_with_retry(_exec)

    def execute_commit(
        self, 
        sql: str, 
        params: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Execute INSERT/UPDATE/DELETE query
        
        Args:
            sql: Raw SQL query string
            params: Query parameters dictionary
            
        Returns:
            Number of affected rows
        """
        def _exec():
            with self.get_session() as session:
                result = session.execute(text(sql), params or {})
                return result.rowcount
        
        return self._run_with_retry(_exec)

    def execute_many(
        self, 
        sql: str, 
        params_list: List[Dict[str, Any]]
    ) -> int:
        """
        Execute query with multiple parameter sets (bulk operations)
        
        Args:
            sql: Raw SQL query string
            params_list: List of parameter dictionaries
            
        Returns:
            Total number of affected rows
        """
        def _exec():
            total_affected = 0
            with self.get_session() as session:
                for params in params_list:
                    result = session.execute(text(sql), params)
                    total_affected += result.rowcount
            return total_affected
        
        return self._run_with_retry(_exec)

    def execute_transaction(
        self, 
        queries_and_params: List[tuple]
    ) -> bool:
        """
        Execute multiple queries in a single transaction
        
        Args:
            queries_and_params: List of (sql, params) tuples
            
        Returns:
            True if transaction succeeded, False otherwise
        """
        def _exec():
            with self.get_session() as session:
                for query, params in queries_and_params:
                    session.execute(text(query), params or {})
                return True
        
        try:
            return self._run_with_retry(_exec)
        except Exception as e:
            return False

    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            result = self.select_scalar("SELECT 1")
            return result == 1
        except Exception as e:
            return False

    def close(self):
        """Close all connections and dispose engine"""
        if hasattr(self, 'engine'):
            self.engine.dispose()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()