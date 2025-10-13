"""
MCP Client Package - Simplified

Using official mcp library for easier implementation.
"""

from tools.mcp_client.client import MCPClient, create_client
from tools.mcp_client.manager import MCPManager, create_manager
from tools.mcp_client.config import (
    create_stdio_server_config,
    create_sse_server_config,
)
from tools.mcp_client.utils import (
    import_mcp_config_json,
    import_mcp_config_file,
    export_mcp_config_json,
    export_mcp_config_file,
    validate_mcp_config,
    sync_server_config,
)

__all__ = [
    # Client
    "MCPClient",
    "create_client",
    # Manager
    "MCPManager",
    "create_manager",
    # Config
    "create_stdio_server_config",
    "create_sse_server_config",
    # Utils
    "import_mcp_config_json",
    "import_mcp_config_file",
    "export_mcp_config_json",
    "export_mcp_config_file",
    "validate_mcp_config",
    "sync_server_config",
]
