from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from common.logger import logger
from data.database.models import BaseEntity 

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
            
            # Create tables
            self._create_tables()
            
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
    
    def _create_tables(self):
        """Create all tables in the database"""
        BaseEntity.metadata.create_all(self.engine)
        logger.info("Database tables created successfully")

    def close(self):
        """Close all connections and dispose engine"""
        if hasattr(self, 'engine'):
            self.engine.dispose()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
