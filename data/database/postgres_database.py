import time
from typing import Optional, Dict, Any, List, Tuple
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError, SQLAlchemyError

import logging
logger = logging.getLogger(__name__)

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
        
        try:
            self.engine = create_engine(
                url,
                echo=echo,
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_timeout=pool_timeout,
                pool_recycle=pool_recycle,
            )
            
            # Create session factory
            self.SessionFactory = sessionmaker(bind=self.engine)
            
            self.retries = retries
            self.retry_delay = retry_delay
            
        except Exception as e:
            logger.error(f"Failed to initialize database connection: {e}")
            raise

    @contextmanager
    def get_session(self):
        """Get a database session with automatic cleanup"""
        session = self.SessionFactory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()

    def _run_with_retry(self, func, *args, **kwargs):
        """Execute function with retry logic for operational errors"""
        last_exception = None
        
        for attempt in range(1, self.retries + 1):
            try:
                return func(*args, **kwargs)
            except (OperationalError, SQLAlchemyError) as e:
                last_exception = e
                if attempt < self.retries:
                    time.sleep(self.retry_delay * attempt)  # Exponential backoff
                else:
                    logger.error(f"Failed to execute function after {self.retries} attempts: {last_exception}")
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
            
        Raises:
            SQLAlchemyError: If query execution fails
        """
        def _exec():
            with self.get_session() as session:
                result = session.execute(text(raw_sql), params or {})
                # Convert to list of dictionaries with better column handling
                if result.returns_rows:
                    columns = result.keys()
                    rows = result.fetchall()
                    return [dict(zip(columns, row)) for row in rows]
                return []
        
        try:
            return self._run_with_retry(_exec)
        except Exception as e:
            logger.error(f"Failed to execute select_all: {e}")
            raise

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
            
        Raises:
            SQLAlchemyError: If query execution fails
        """
        def _exec():
            with self.get_session() as session:
                result = session.execute(text(raw_sql), params or {})
                row = result.fetchone()
                if row and result.returns_rows:
                    columns = result.keys()
                    return dict(zip(columns, row))
                return None
        
        try:
            return self._run_with_retry(_exec)
        except Exception as e:
            logger.error(f"Failed to execute select_one: {e}")
            raise

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
            
        Raises:
            SQLAlchemyError: If query execution fails
        """
        def _exec():
            with self.get_session() as session:
                result = session.execute(text(raw_sql), params or {})
                return result.scalar()
        
        try:
            return self._run_with_retry(_exec)
        except Exception as e:
            logger.error(f"Failed to execute select_scalar: {e}")
            raise

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
            
        Raises:
            SQLAlchemyError: If query execution fails
        """
        def _exec():
            with self.get_session() as session:
                result = session.execute(text(sql), params or {})
                affected_rows = result.rowcount
                return affected_rows
        
        try:
            return self._run_with_retry(_exec)
        except Exception as e:
            logger.error(f"Failed to execute execute_commit: {e}")
            raise

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
            
        Raises:
            SQLAlchemyError: If query execution fails
        """
        def _exec():
            with self.get_session() as session:
                # Use executemany for better performance
                result = session.execute(text(sql), params_list)
                affected_rows = result.rowcount
                return affected_rows
        
        try:
            return self._run_with_retry(_exec)
        except Exception as e:
            logger.error(f"Failed to execute execute_many: {e}")
            raise

    def execute_transaction(
        self, 
        queries_and_params: List[Tuple[str, Optional[Dict[str, Any]]]]
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
                total_affected = 0
                for query, params in queries_and_params:
                    result = session.execute(text(query), params or {})
                    total_affected += result.rowcount
                
                return True
        
        try:
            return self._run_with_retry(_exec)
        except Exception as e:
            logger.error(f"Failed to execute execute_transaction: {e}")
            raise

    def execute_raw(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Execute any raw SQL and return the result object
        
        Args:
            sql: Raw SQL query string
            params: Query parameters dictionary
            
        Returns:
            Raw result object from SQLAlchemy
            
        Raises:
            SQLAlchemyError: If query execution fails
        """
        def _exec():
            with self.get_session() as session:
                return session.execute(text(sql), params or {})
        
        try:
            return self._run_with_retry(_exec)
        except Exception as e:
            logger.error(f"Failed to execute execute_raw: {e}")
            raise

    async def health_check(self) -> bool:
        """
        Check database health
        
        Returns:
            True if database is healthy, False otherwise
        """
        try:
            result = self.select_scalar("SELECT 1")
            is_healthy = result == 1
            return is_healthy
        except Exception as e:
            logger.error(f"Failed to execute health_check: {e}")
            return False

    def get_connection_info(self) -> Dict[str, Any]:
        """
        Get information about current connection pool
        
        Returns:
            Dictionary with connection pool statistics
        """
        pool = self.engine.pool
        return {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "invalid": pool.invalid(),
        }

    def close(self):
        """Close all connections and dispose engine"""
        if hasattr(self, 'engine'):
            self.engine.dispose()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
