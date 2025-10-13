"""
MCP Client Configuration

Helper functions for creating MCP server configurations.
"""

from typing import Dict, Any, List
from data.database.models.mcp_servers import TransportType


def create_stdio_server_config(
    name: str,
    command: str,
    args: List[str] = None,
    display_name: str = None,
    description: str = None,
    env: Dict[str, str] = None,
    priority: int = 0,
    is_active: bool = True,
) -> Dict[str, Any]:
    """
    Create STDIO MCP server configuration

    Args:
        name: Unique server name
        command: Command to execute (e.g., "npx", "python", "node")
        args: Command arguments
        display_name: Display name (defaults to name)
        description: Server description
        env: Environment variables
        priority: Server priority (higher loads first)
        is_active: Whether server is active

    Returns:
        Configuration dictionary for MCPServer model
    """
    return {
        "name": name,
        "display_name": display_name or name,
        "description": description,
        "transport_type": TransportType.STDIO,
        "command": command,
        "args": args or [],
        "env": env,
        "priority": priority,
        "is_active": is_active,
    }


def create_sse_server_config(
    name: str,
    url: str,
    headers: Dict[str, str] = None,
    display_name: str = None,
    description: str = None,
    priority: int = 0,
    is_active: bool = True,
) -> Dict[str, Any]:
    """
    Create SSE MCP server configuration

    Args:
        name: Unique server name
        url: SSE endpoint URL
        headers: HTTP headers for requests
        display_name: Display name (defaults to name)
        description: Server description
        priority: Server priority (higher loads first)
        is_active: Whether server is active

    Returns:
        Configuration dictionary for MCPServer model
    """
    return {
        "name": name,
        "display_name": display_name or name,
        "description": description,
        "transport_type": TransportType.SSE,
        "url": url,
        "headers": headers,
        "priority": priority,
        "is_active": is_active,
    }
