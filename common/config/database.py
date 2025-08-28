"""
Database configuration using SQLAlchemy with async support
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

from .settings import settings

# Create base class for models
Base = declarative_base()

# Create async database engine
engine = create_async_engine(
    settings.database.url,
    echo=settings.debug,
    pool_size=20,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_use_lifo=True,  # Use LIFO queue for better connection reuse
    connect_args={"server_settings": {"application_name": settings.app_name}}
)

# Create async session factory
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    future=True
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting async database session.
    
    Usage:
        async with get_db() as session:
            result = await session.execute(select(User))
            user = result.scalars().first()
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_models():
    """Initialize database models (create tables)"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections"""
    if engine is not None:
        await engine.dispose()


# For backward compatibility
get_database_session = get_db
init_database = init_models
close_database = close_db
