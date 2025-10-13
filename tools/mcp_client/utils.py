"""
MCP Client Utilities

Helper functions for importing/exporting MCP configurations
in standard format (compatible with Claude Desktop config)
"""

import json
from typing import Dict, Any, List
from pathlib import Path

from common.logger import logger
from data.database.database import PostgresDatabase
from data.database.models import MCPServer


def import_mcp_config_json(
    config_data: Dict[str, Any],
    database: PostgresDatabase,
    default_priority: int = 0,
    default_enabled: bool = True,
) -> List[str]:
    """
    Import MCP servers from standard config JSON format

    Expected format:
    {
        "mcpServers": {
            "server-name": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem"],
                "env": {"KEY": "value"}
            },
            "other-server": {
                "url": "http://localhost:5173/api/mcp",
                "headers": {
                    "mcp-api-key": "..."
                }
            }
        }
    }

    Args:
        config_data: Config dictionary in standard format
        database: Database instance
        default_priority: Default priority for imported servers
        default_enabled: Whether to enable servers by default

    Returns:
        List of imported server names
    """
    imported = []

    if "mcpServers" not in config_data:
        logger.error("Invalid config format: missing 'mcpServers' key")
        return imported

    mcp_servers = config_data["mcpServers"]

    with database.get_session() as session:
        for server_name, server_config in mcp_servers.items():
            try:
                # Check if server already exists
                existing = (
                    session.query(MCPServer)
                    .filter(MCPServer.name == server_name)
                    .first()
                )

                if existing:
                    logger.warning(f"Server '{server_name}' already exists, skipping")
                    continue

                # Create new server from config
                server = MCPServer.from_mcp_json(
                    name=server_name,
                    display_name=server_name,  # Use name as display_name by default
                    config=server_config,
                    priority=default_priority,
                    is_active=default_enabled,
                )

                session.add(server)
                imported.append(server_name)
                logger.info(f"Imported MCP server: {server_name}")

            except Exception as e:
                logger.error(f"Failed to import server '{server_name}': {e}")
                continue

        session.commit()

    logger.info(f"Successfully imported {len(imported)} MCP servers")
    return imported


def import_mcp_config_file(
    config_path: str,
    database: PostgresDatabase,
    default_priority: int = 0,
    default_enabled: bool = True,
) -> List[str]:
    """
    Import MCP servers from JSON config file

    Args:
        config_path: Path to config JSON file
        database: Database instance
        default_priority: Default priority for imported servers
        default_enabled: Whether to enable servers by default

    Returns:
        List of imported server names
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        logger.info(f"Loading MCP config from: {config_path}")
        return import_mcp_config_json(config_data, database, default_priority, default_enabled)

    except FileNotFoundError:
        logger.error(f"Config file not found: {config_path}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file: {e}")
        return []
    except Exception as e:
        logger.error(f"Failed to import config file: {e}")
        return []


def export_mcp_config_json(database: PostgresDatabase) -> Dict[str, Any]:
    """
    Export all MCP servers to standard config JSON format

    Returns format:
    {
        "mcpServers": {
            "server-name": {
                "command": "npx",
                "args": [...],
                "env": {...}
            },
            ...
        }
    }

    Args:
        database: Database instance

    Returns:
        Config dictionary in standard format
    """
    config = {"mcpServers": {}}

    with database.get_session() as session:
        servers = session.query(MCPServer).all()

        for server in servers:
            config["mcpServers"][server.name] = server.to_mcp_json()

    return config


def export_mcp_config_file(
    database: PostgresDatabase,
    output_path: str,
    indent: int = 2,
) -> bool:
    """
    Export all MCP servers to JSON config file

    Args:
        database: Database instance
        output_path: Path to output JSON file
        indent: JSON indentation (default: 2)

    Returns:
        True if export successful
    """
    try:
        config = export_mcp_config_json(database)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=indent, ensure_ascii=False)

        logger.info(f"Exported {len(config['mcpServers'])} servers to: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to export config file: {e}")
        return False


def sync_server_config(
    database: PostgresDatabase,
    server_name: str,
    config: Dict[str, Any],
) -> bool:
    """
    Sync/update a single server config from JSON format

    If server exists, updates it. If not, creates it.

    Args:
        database: Database instance
        server_name: Server name
        config: Server config in standard format

    Returns:
        True if sync successful
    """
    try:
        with database.get_session() as session:
            existing = (
                session.query(MCPServer)
                .filter(MCPServer.name == server_name)
                .first()
            )

            if existing:
                # Update existing server
                if "command" in config:
                    existing.command = config.get("command")
                    existing.args = config.get("args", [])
                    existing.env = config.get("env")
                elif "url" in config:
                    existing.url = config.get("url")
                    existing.headers = config.get("headers")

                logger.info(f"Updated server config: {server_name}")
            else:
                # Create new server
                server = MCPServer.from_mcp_json(
                    name=server_name,
                    display_name=server_name,  # Use name as display_name by default
                    config=config,
                )
                session.add(server)
                logger.info(f"Created new server: {server_name}")

            session.commit()
            return True

    except Exception as e:
        logger.error(f"Failed to sync server config: {e}")
        return False


def validate_mcp_config(config_data: Dict[str, Any]) -> tuple[bool, List[str]]:
    """
    Validate MCP config JSON format

    Args:
        config_data: Config dictionary to validate

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Check top level structure
    if not isinstance(config_data, dict):
        errors.append("Config must be a dictionary")
        return False, errors

    if "mcpServers" not in config_data:
        errors.append("Missing 'mcpServers' key")
        return False, errors

    mcp_servers = config_data["mcpServers"]
    if not isinstance(mcp_servers, dict):
        errors.append("'mcpServers' must be a dictionary")
        return False, errors

    # Validate each server
    for server_name, server_config in mcp_servers.items():
        if not isinstance(server_config, dict):
            errors.append(f"Server '{server_name}' config must be a dictionary")
            continue

        # Must have either command or url
        has_command = "command" in server_config
        has_url = "url" in server_config

        if not has_command and not has_url:
            errors.append(f"Server '{server_name}' must have 'command' or 'url'")

        if has_command and has_url:
            errors.append(f"Server '{server_name}' cannot have both 'command' and 'url'")

        # Validate STDIO config
        if has_command:
            if not isinstance(server_config["command"], str):
                errors.append(f"Server '{server_name}' command must be a string")

            args = server_config.get("args", [])
            if not isinstance(args, list):
                errors.append(f"Server '{server_name}' args must be a list")

            env = server_config.get("env")
            if env is not None and not isinstance(env, dict):
                errors.append(f"Server '{server_name}' env must be a dictionary")

        # Validate SSE config
        if has_url:
            if not isinstance(server_config["url"], str):
                errors.append(f"Server '{server_name}' url must be a string")

            headers = server_config.get("headers")
            if headers is not None and not isinstance(headers, dict):
                errors.append(f"Server '{server_name}' headers must be a dictionary")

    is_valid = len(errors) == 0
    return is_valid, errors


def create_example_config() -> Dict[str, Any]:
    """
    Create an example MCP config for reference

    Returns:
        Example config dictionary
    """
    return {
        "mcpServers": {
            "filesystem": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/directory"],
                "env": {}
            },
            "github": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
                "env": {
                    "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_your_token_here"
                }
            },
            "postgres": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-postgres", "postgresql://user:pass@localhost/db"]
            },
            "oasm-platform": {
                "url": "http://localhost:5173/api/mcp",
                "headers": {
                    "mcp-api-key": "your-api-key-here"
                }
            },
            "custom-api": {
                "url": "https://api.example.com/mcp",
                "headers": {
                    "Authorization": "Bearer your-token",
                    "X-Custom-Header": "value"
                }
            }
        }
    }
