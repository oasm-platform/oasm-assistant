from sqlmodel import Field, Relationship, Column
from typing import Optional, List
from .base import BaseEntity
import sqlalchemy as sa

class Port(BaseEntity, table=True):
    __tablename__ = "ports"
    
    ports: List[int] = Field(sa_column=Column("ports", sa.ARRAY(sa.Integer)))
    
    # Foreign Keys
    asset_id: Optional[str] = Field(foreign_key="assets.id")
    job_history_id: Optional[str] = Field(foreign_key="job_histories.id")
    
    # Relationships
    asset: Optional["Asset"] = Relationship(back_populates="ports")
    job_history: Optional["JobHistory"] = Relationship(back_populates="ports")