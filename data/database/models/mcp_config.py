"""MCP Configuration model - stores Claude Desktop format JSON"""

from sqlalchemy import Column, JSON, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from uuid import uuid4
from .base import BaseEntity


class MCPConfig(BaseEntity):
    """
    Store MCP configuration in Claude Desktop format
    One row per (workspace_id, user_id) pair

    config_json format (Claude Desktop compatible):
    {
      "mcpServers": {
        "server-name-1": {
          "url": "http://...",
          "headers": {"api-key": "..."}
        },
        "server-name-2": {
          "command": "npx",
          "args": ["-y", "package"],
          "env": {"KEY": "value"}
        }
      }
    }
    """
    __tablename__ = "mcp_configs"
    __table_args__ = (
        UniqueConstraint('workspace_id', 'user_id', name='uq_workspace_user'),
        Index('idx_mcp_workspace_user', 'workspace_id', 'user_id'),
        {'extend_existing': True}
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    config_json = Column(JSON, nullable=False, default=lambda: {"mcpServers": {}})

    @property
    def servers(self) -> dict:
        """Get mcpServers dict"""
        return self.config_json.get("mcpServers", {})

    def add_server(self, name: str, server_config: dict):
        """Add or update a server in the config"""
        if "mcpServers" not in self.config_json:
            self.config_json["mcpServers"] = {}
        self.config_json["mcpServers"][name] = server_config

    def remove_server(self, name: str):
        """Remove a server from the config"""
        if "mcpServers" in self.config_json:
            self.config_json["mcpServers"].pop(name, None)

    def get_server(self, name: str) -> dict:
        """Get a specific server config"""
        return self.config_json.get("mcpServers", {}).get(name, {})

    def list_server_names(self) -> list:
        """List all server names"""
        return list(self.config_json.get("mcpServers", {}).keys())

    def __repr__(self) -> str:
        server_count = len(self.servers)
        return f"<MCPConfig(workspace={self.workspace_id}, user={self.user_id}, servers={server_count})>"
