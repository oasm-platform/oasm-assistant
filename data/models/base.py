from sqlalchemy import Column, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import UUID
from uuid import uuid4
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class BaseEntity(Base):
    __abstract__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    createdAt = Column(TIMESTAMP(timezone=True), 
        nullable=False, 
        server_default=func.now())
    updatedAt = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
