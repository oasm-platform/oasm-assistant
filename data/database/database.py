from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from common.logger import logger
from data.database.models import BaseEntity

class PostgresDatabase:
    """PostgreSQL database connection manager with Async support"""
    
    def __init__(
        self,
        url: str,
        echo: bool = False,
        pool_size: int = 20,
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
        """
        try:
            # Ensure we use the async driver
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg://")
            
            self.engine = create_async_engine(
                url,
                echo=echo,
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_timeout=pool_timeout,
                pool_recycle=pool_recycle,
            )
            
            # Create async session factory
            self.AsyncSessionFactory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False
            )
            
            self.retries = retries
            self.retry_delay = retry_delay
            
        except Exception as e:
            logger.error("Failed to initialize database connection: {}", e)
            raise

    async def initialize(self):
        """Initialize database: create tables and run migrations"""
        await self._run_migrations()
        await self._create_tables()

    @asynccontextmanager
    async def get_session(self):
        """Get an async database session with automatic cleanup"""
        session = self.AsyncSessionFactory()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def health_check(self) -> bool:
        """Check database health"""
        try:
            async with self.get_session() as session:
                result = await session.execute(text("SELECT 1"))
                return result.scalar() == 1
        except Exception as e:
            logger.error("Failed to execute health_check: {}", e)
            return False
    
    async def _create_tables(self):
        """Create all tables in the database if they don't exist"""
        async with self.engine.begin() as conn:
            await conn.run_sync(BaseEntity.metadata.create_all)
        logger.info("Database tables checked/created successfully")

    async def _run_migrations(self):
        """Run initial database migrations, like creating extensions."""
        try:
            async with self.get_session() as session:
                await session.execute(text('CREATE EXTENSION IF NOT EXISTS vector;'))
                await session.commit()
            logger.debug("Successfully ran database migrations (CREATE EXTENSION vector).")
        except Exception as e:
            logger.warning("Could not run database migrations: {}. This might be fine if the user does not have superuser privileges.", e)

    async def close(self):
        """Close all connections and dispose engine"""
        if hasattr(self, 'engine'):
            await self.engine.dispose()

