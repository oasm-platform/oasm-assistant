from sqlalchemy import Column, String, Boolean, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from .base import BaseEntity
from uuid import uuid4

class LLMConfig(BaseEntity):
    """
    Store LLM configuration (API keys, models) for LLM providers.
    Scoped by workspace_id and user_id.
    """
    __tablename__ = "llm_configs"
    __table_args__ = (
        Index('idx_llm_configs_workspace_user', 'workspace_id', 'user_id'),
        {'extend_existing': True}
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    provider = Column(String(50), nullable=False) # e.g., "openai", "anthropic", "google"
    api_key = Column(String(255), nullable=True)
    model = Column(String(100), nullable=True) # Optional default model for this provider
    is_preferred = Column(Boolean, default=False, nullable=False) # Only one can be preferred per user/workspace

    def __repr__(self) -> str:
        return f"<LLMConfig(workspace={self.workspace_id}, user={self.user_id}, provider={self.provider}, model={self.model})>"
