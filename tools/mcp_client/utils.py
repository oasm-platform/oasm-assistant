"""MCP client utilities - config parsing and connection building"""

from typing import Dict, Tuple, List, Any
from uuid import UUID
from dataclasses import dataclass, field

from data.database.models import MCPConfig


@dataclass(frozen=True)
class MCPConnection:
    """
    Connection info for an MCP server

    NOT a k8s/docker instance - just connection metadata.
    The actual server can run anywhere (local/k8s/cloud).
    """
    name: str
    workspace_id: UUID
    user_id: UUID
    transport_type: str
    url: str = ""
    command: str = ""
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    api_key: str = ""

    @property
    def display_name(self) -> str:
        return self.name.replace('-', ' ').title()


def parse_server_config(name: str, server_config: dict) -> Tuple[str, dict]:
    """Parse individual server from Claude Desktop format"""
    if "url" in server_config:
        config = {
            "name": name,
            "transport_type": "sse",
            "url": server_config["url"]
        }
        if "headers" in server_config:
            config["headers"] = server_config["headers"]
        return "sse", config

    elif "command" in server_config:
        config = {
            "name": name,
            "transport_type": "stdio",
            "command": server_config["command"]
        }
        if "args" in server_config:
            config["args"] = server_config["args"]
        if "env" in server_config:
            config["env"] = server_config["env"]
        return "stdio", config

    return None, {}


def create_mcp_config(config_json: Dict, workspace_id: UUID, user_id: UUID) -> MCPConfig:
    """Create MCPConfig from Claude Desktop format"""
    return MCPConfig(workspace_id=workspace_id, user_id=user_id, config_json=config_json)


def mcp_config_to_connections(mcp_config: MCPConfig) -> List[MCPConnection]:
    """Convert MCPConfig to list of MCPConnection objects"""
    connections = []
    for name, server_config in mcp_config.servers.items():
        _, parsed_config = parse_server_config(name, server_config)
        if parsed_config:
            connections.append(MCPConnection(
                name=name,
                workspace_id=mcp_config.workspace_id,
                user_id=mcp_config.user_id,
                transport_type=parsed_config["transport_type"],
                url=parsed_config.get("url", ""),
                command=parsed_config.get("command", ""),
                args=parsed_config.get("args", []),
                env=parsed_config.get("env", {}),
                headers=parsed_config.get("headers", {})
            ))
    return connections


def build_connection_config(conn: MCPConnection) -> Dict[str, Any]:
    """Build config dict for langchain-mcp-adapters"""
    transport = conn.transport_type

    if transport == 'stdio':
        return {
            "command": conn.command,
            "args": conn.args,
            "env": conn.env,
            "transport": "stdio"
        }

    if transport in ('sse', 'http', 'streamable_http'):
        config = {
            "url": conn.url,
            "transport": "sse" if transport == 'sse' else "streamable_http"
        }

        headers = conn.headers.copy() if conn.headers else {}
        if conn.api_key and 'Authorization' not in headers:
            headers['Authorization'] = f"Bearer {conn.api_key}"
        if headers:
            config["headers"] = headers

        return config

    raise ValueError(f"Unsupported transport: {transport}")
