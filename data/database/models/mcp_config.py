"""MCP Configuration model - stores Claude Desktop format JSON"""

from sqlalchemy import Column, JSON, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm.attributes import flag_modified
from uuid import uuid4
from .base import BaseEntity


class MCPConfig(BaseEntity):
    """
    Store MCP configuration in Claude Desktop format
    One row per (workspace_id, user_id) pair

    config_json format (Claude Desktop compatible + disabled flag):
    {
      "mcpServers": {
        "server-name-1": {
          "url": "http://...",
          "headers": {"api-key": "..."},
          "disabled": false  // Optional: default false if not present (enabled)
        },
        "server-name-2": {
          "command": "npx",
          "args": ["-y", "package"],
          "env": {"KEY": "value"},
          "disabled": true  // Server is disabled/stopped
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

        # Ensure 'disabled' field exists (default to False if not specified - enabled by default)
        if "disabled" not in server_config:
            server_config["disabled"] = False

        self.config_json["mcpServers"][name] = server_config
        # Mark the JSON field as modified so SQLAlchemy tracks the change
        flag_modified(self, "config_json")

    def remove_server(self, name: str):
        """Remove a server from the config"""
        if "mcpServers" in self.config_json:
            self.config_json["mcpServers"].pop(name, None)
            # Mark the JSON field as modified so SQLAlchemy tracks the change
            flag_modified(self, "config_json")

    def get_server(self, name: str) -> dict:
        """Get a specific server config"""
        return self.config_json.get("mcpServers", {}).get(name, {})

    def list_server_names(self) -> list:
        """List all server names"""
        return list(self.config_json.get("mcpServers", {}).keys())

    def is_server_disabled(self, name: str) -> bool:
        """Check if a server is disabled (not allowed to operate)"""
        server_config = self.get_server(name)
        # Default to False if 'disabled' field not present (enabled by default)
        return server_config.get("disabled", False)

    def set_server_disabled(self, name: str, disabled: bool):
        """Enable or disable a server"""
        if "mcpServers" in self.config_json and name in self.config_json["mcpServers"]:
            self.config_json["mcpServers"][name]["disabled"] = disabled
            flag_modified(self, "config_json")

    def __repr__(self) -> str:
        server_count = len(self.servers)
        return f"<MCPConfig(workspace={self.workspace_id}, user={self.user_id}, servers={server_count})>"
