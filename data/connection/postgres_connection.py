from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from typing import Generator

from common.config.settings import settings

class DatabaseManager:
    def __init__(self):
        self.database_url = settings.postgres.url
        
        # Sync engine
        self.engine = create_engine(
            self.database_url,
            echo=False,
            pool_size=20,
            max_overflow=0
        )
        
        # Async engine
        self.async_engine = create_async_engine(
            self.database_url,
            echo=False,
            pool_size=20,
            max_overflow=0
        )
        
        # Session makers
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
            class_=Session
        )
        
        self.AsyncSessionLocal = sessionmaker(
            self.async_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    
    def get_session(self) -> Generator[Session, None, None]:
        """Get sync database session"""
        session = self.SessionLocal()
        try:
            yield session
        finally:
            session.close()
    
    async def get_async_session(self) -> AsyncSession:
        """Get async database session"""
        async with self.AsyncSessionLocal() as session:
            yield session
    
    def create_tables(self):
        """Create all tables"""
        SQLModel.metadata.create_all(self.engine)