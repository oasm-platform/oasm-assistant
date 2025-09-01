from sqlmodel import Field, Relationship
from typing import Optional, List, Dict, Any
from .base import BaseEntity

class Asset(BaseEntity, table=True):
    __tablename__ = "assets"
    
    value: str
    target_id: Optional[str] = Field(foreign_key="targets.id")
    is_primary: bool = Field(default=False)
    dns_records: Optional[Dict[str, Any]] = Field(default=None, sa_column_kwargs={"type_": "JSON"})
    is_error_page: bool = Field(default=False)
    
    # Relationships
    target: Optional["Target"] = Relationship(back_populates="assets")
    jobs: List["Job"] = Relationship(back_populates="asset")
    ports: List["Port"] = Relationship(back_populates="asset")
    http_responses: List["HttpResponse"] = Relationship(back_populates="asset")
    vulnerabilities: List["Vulnerability"] = Relationship(back_populates="asset")