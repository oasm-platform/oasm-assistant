from sqlalchemy import Column, TIMESTAMP, func, inspect
import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from uuid import uuid4
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class BaseEntity(Base):
    __abstract__ = True
    
    created_at = Column("created_at", TIMESTAMP(timezone=True),
         nullable=False,
         server_default=func.now())
         
    updated_at = Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def to_dict(self):
        """Convert to dictionary with all fields"""
        result = {}
        
        for column in inspect(self).mapper.column_attrs:
            column_name = column.key
            value = getattr(self, column_name)
            
            if isinstance(value, datetime):
                result[column_name] = value.isoformat()
            elif isinstance(value, uuid.UUID):
                result[column_name] = str(value)
            elif value is None:
                result[column_name] = None
            else:
                result[column_name] = value
                
        return result 