from sqlalchemy import Column, String, Integer, Boolean, JSON, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from uuid import uuid4
from data.database.models.base import BaseEntity
from enum import Enum


class TransportType(str, Enum):
    STDIO = 'stdio'
    SSE = 'sse'
    HTTP = 'http'


class MCPServer(BaseEntity):
    __tablename__ = "mcp_servers"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Basic information
    name = Column(String(255), nullable=False, unique=True, index=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Server type and configuration
    transport_type = Column(
        SQLEnum(TransportType, name='transport_type_enum', create_type=True),
        nullable=False
    )
    
    # STDIO configuration
    command = Column(String(500), nullable=True)
    args = Column(JSON, nullable=True)
    env = Column(JSON, nullable=True)
    
    # SSE/HTTP configuration
    url = Column(String(500), nullable=True)
    api_key = Column(String(255), nullable=True)
    headers = Column(JSON, nullable=True)
    
    # Metadata and capabilities
    version = Column(String(50), nullable=True)
    capabilities = Column(JSON, nullable=True)
    config = Column(JSON, nullable=True)
    
    # Status and settings
    is_active = Column(Boolean, default=True, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    priority = Column(Integer, default=0, nullable=False)
    
    
    def __repr__(self):
        return f"<MCPServer(id={self.id}, name={self.name}, type={self.transport_type})>"
    
    def to_dict(self):
        """Convert to dict with sensitive data hidden"""
        result = super().to_dict()
        
        # Hide sensitive information
        if result.get('api_key'):
            result['api_key'] = '***HIDDEN***'
            
        return result
    
    def get_connection_config(self):
        """Get connection config based on transport type"""
        if self.transport_type == TransportType.STDIO:
            return {
                'type': 'stdio',
                'command': self.command,
                'args': self.args or [],
                'env': self.env or {}
            }
        elif self.transport_type in [TransportType.SSE, TransportType.HTTP]:
            config = {
                'type': self.transport_type.value,
                'url': self.url,
                'headers': self.headers or {}
            }
            if self.api_key:
                config['headers']['Authorization'] = f'Bearer {self.api_key}'
            return config
        return None
    
    def to_mcp_json(self):
        """
        Convert to standard MCP JSON format (Claude Desktop compatible)
        Returns config ready to use with MCP client
        """
        if self.transport_type == TransportType.STDIO:
            config = {
                'command': self.command,
                'args': self.args or []
            }
            if self.env:
                config['env'] = self.env
            return config
        else:  # SSE or HTTP
            config = {'url': self.url}
            if self.headers or self.api_key:
                headers = self.headers.copy() if self.headers else {}
                if self.api_key:
                    headers['Authorization'] = f'Bearer {self.api_key}'
                config['headers'] = headers
            return config
    
    @classmethod
    def from_mcp_json(cls, name: str, display_name: str, config: dict, **kwargs):
        """
        Create MCPServer from MCP JSON config
        
        Example:
            MCPServer.from_mcp_json(
                "filesystem",
                "File System",
                {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem"]}
            )
        """
        # Detect transport type
        if 'command' in config:
            return cls(
                name=name,
                display_name=display_name,
                transport_type=TransportType.STDIO,
                command=config.get('command'),
                args=config.get('args', []),
                env=config.get('env'),
                **kwargs
            )
        elif 'url' in config:
            headers = config.get('headers', {})
            api_key = None
            
            # Extract API key from Authorization header
            if 'Authorization' in headers:
                auth = headers['Authorization']
                if auth.startswith('Bearer '):
                    api_key = auth[7:]
                    headers = {k: v for k, v in headers.items() if k != 'Authorization'}
            
            return cls(
                name=name,
                display_name=display_name,
                transport_type=TransportType.SSE,
                url=config.get('url'),
                api_key=api_key,
                headers=headers if headers else None,
                **kwargs
            )
        else:
            raise ValueError("Invalid MCP config: must contain 'command' or 'url'")
    
    @classmethod
    def create_stdio(cls, name: str, display_name: str, command: str, 
                     args: list = None, env: dict = None, **kwargs):
        """Convenience method to create STDIO server"""
        return cls(
            name=name,
            display_name=display_name,
            transport_type=TransportType.STDIO,
            command=command,
            args=args,
            env=env,
            **kwargs
        )
    
    @classmethod
    def create_sse(cls, name: str, display_name: str, url: str, 
                   api_key: str = None, headers: dict = None, **kwargs):
        """Convenience method to create SSE server"""
        return cls(
            name=name,
            display_name=display_name,
            transport_type=TransportType.SSE,
            url=url,
            api_key=api_key,
            headers=headers,
            **kwargs
        )