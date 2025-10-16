from sqlalchemy import Column, JSON, Index, Boolean, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from uuid import uuid4
from .base import BaseEntity
from enum import Enum


class ServerStatus(str, Enum):
    """Server status enum"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DISABLED = "disabled"    


class MCPServer(BaseEntity):
    """
    Simplified MCP Server model - stores all configuration in JSON

    mcp_config schema:
    {
        "name": "server-name",
        "display_name": "Display Name",
        "description": "Description",
        "transport_type": "stdio|sse|http",
        "command": "npx",  # For STDIO
        "args": ["-y", "@modelcontextprotocol/server"],  # For STDIO
        "env": {"KEY": "value"},  # For STDIO
        "url": "https://api.example.com",  # For SSE/HTTP
        "headers": {
            "X-Custom": "value",
            "api-key": "value"
            },  # For SSE/HTTP
        "version": "1.0.0",
        "capabilities": {},
        "is_active": true,
        "is_default": false,
        "priority": 0
    }
    """
    __tablename__ = "mcp_servers"
    __table_args__ = (
        Index('idx_workspace_user', 'workspace_id', 'user_id'),
        {'extend_existing': True}
    )
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Workspace and user association
    workspace_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # All configuration stored as JSON
    mcp_config = Column(JSON, nullable=False)

    server_status = Column(String(20), nullable=False, default=ServerStatus.INACTIVE.value)
    
    # Property helpers for easy access to mcp_config fields
    @property
    def name(self) -> str:
        """Get server name from config"""
        return self.mcp_config.get('name', '')

    @property
    def display_name(self) -> str:
        """Get display name from config"""
        return self.mcp_config.get('display_name', self.name)

    @property
    def description(self) -> str:
        """Get description from config"""
        return self.mcp_config.get('description', '')

    @property
    def transport_type(self) -> str:
        """Get transport type from config"""
        return self.mcp_config.get('transport_type', 'stdio')

    @property
    def command(self) -> str:
        """Get command from config (for STDIO)"""
        return self.mcp_config.get('command', '')

    @property
    def args(self) -> list:
        """Get args from config (for STDIO)"""
        return self.mcp_config.get('args', [])

    @property
    def env(self) -> dict:
        """Get env from config (for STDIO)"""
        return self.mcp_config.get('env', {})

    @property
    def url(self) -> str:
        """Get URL from config (for SSE/HTTP)"""
        return self.mcp_config.get('url', '')

    @property
    def headers(self) -> dict:
        """Get headers from config (for SSE/HTTP)"""
        return self.mcp_config.get('headers', {})

    @property
    def version(self) -> str:
        """Get version from config"""
        return self.mcp_config.get('version', '')

    @property
    def capabilities(self) -> dict:
        """Get capabilities from config"""
        return self.mcp_config.get('capabilities', {})

    @property
    def priority(self) -> int:
        """Get priority from config"""
        return self.mcp_config.get('priority', 0)

    @property
    def is_default(self) -> bool:
        """Get is_default from config"""
        return self.mcp_config.get('is_default', False)

    @property
    def api_key(self) -> str:
        """Get API key from config (for SSE/HTTP)"""
        return self.mcp_config.get('api_key', '')

    def __repr__(self) -> str:
        """String representation for debugging"""
        return f"<MCPServer(id={self.id}, name='{self.name}', type={self.transport_type}, status={self.server_status})>"

    def validate_config(self) -> tuple[bool, str]:
        """
        Validate mcp_config structure
        Returns: (is_valid, error_message)
        """
        if not isinstance(self.mcp_config, dict):
            return False, "mcp_config must be a dictionary"

        # Check required fields
        if not self.mcp_config.get('name'):
            return False, "mcp_config must contain 'name' field"

        transport_type = self.mcp_config.get('transport_type', 'stdio')

        # Validate based on transport type
        if transport_type == 'stdio':
            if not self.mcp_config.get('command'):
                return False, "STDIO server must have 'command' field"
        elif transport_type in ['sse', 'http']:
            if not self.mcp_config.get('url'):
                return False, f"{transport_type.upper()} server must have 'url' field"
        else:
            return False, f"Invalid transport_type: {transport_type}. Must be 'stdio', 'sse', or 'http'"

        return True, ""

    def get_connection_config(self) -> dict:
        """
        Get connection config ready for MCP client
        Returns config dict suitable for MCPManager._connect()
        """
        transport_type = self.transport_type

        if transport_type == 'stdio':
            config = {
                'transport_type': 'stdio',
                'command': self.command,
                'args': self.args or [],
            }
            if self.env:
                config['env'] = self.env
            return config

        elif transport_type in ['sse', 'http']:
            config = {
                'transport_type': transport_type,
                'url': self.url,
            }
            if self.headers or self.api_key:
                headers = self.headers.copy() if self.headers else {}
                if self.api_key:
                    headers['Authorization'] = f'Bearer {self.api_key}'
                config['headers'] = headers
            return config

        return {}
