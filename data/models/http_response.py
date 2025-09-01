from sqlmodel import Field, Relationship, Column
from typing import Optional, List, Dict
from datetime import datetime
from .base import BaseEntity
from .tls_info import TlsInfo
from .knowledgebase_info import KnowledgebaseInfo
import sqlalchemy as sa

class HttpResponse(BaseEntity, table=True):
    __tablename__ = "http_responses"
    
    timestamp: Optional[datetime] = Field(default=None)
    tls: Optional[TlsInfo] = Field(default=None, sa_column=Column("tls", sa.JSON))
    port: Optional[str] = None
    url: Optional[str] = None
    input: Optional[str] = None
    title: Optional[str] = None
    scheme: Optional[str] = None
    webserver: Optional[str] = None
    body: Optional[str] = None
    content_type: Optional[str] = None
    method: Optional[str] = None
    host: Optional[str] = None
    path: Optional[str] = None
    favicon: Optional[str] = None
    favicon_md5: Optional[str] = None
    favicon_url: Optional[str] = None
    header: Optional[Dict[str, str]] = Field(default=None, sa_column=Column("header", sa.JSON))
    raw_header: Optional[str] = None
    request: Optional[str] = None
    time: Optional[str] = None
    a: Optional[List[str]] = Field(default=None, sa_column=Column("a", sa.ARRAY(sa.String)))
    tech: Optional[List[str]] = Field(default=None, sa_column=Column("tech", sa.ARRAY(sa.String)))
    words: Optional[int] = None
    lines: Optional[int] = None
    status_code: Optional[int] = None
    content_length: Optional[int] = None
    failed: bool = Field(default=False)
    knowledgebase: Optional[KnowledgebaseInfo] = Field(default=None, sa_column=Column("knowledgebase", sa.JSON))
    resolvers: Optional[List[str]] = Field(default=None, sa_column=Column("resolvers", sa.ARRAY(sa.String)))
    chain_status_codes: Optional[List[str]] = Field(default=None, sa_column=Column("chain_status_codes", sa.ARRAY(sa.String)))
    
    # Foreign Keys
    asset_id: Optional[str] = Field(foreign_key="assets.id")
    job_history_id: Optional[str] = Field(foreign_key="job_histories.id")
    
    # Relationships
    asset: Optional["Asset"] = Relationship(back_populates="http_responses")
    job_history: Optional["JobHistory"] = Relationship(back_populates="http_responses")