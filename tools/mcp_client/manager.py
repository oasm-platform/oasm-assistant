"""
MCP Manager using langchain-mcp-adapters

This module provides a manager for handling multiple MCP server connections.
"""

from typing import Dict, List, Optional, Any
from uuid import UUID
from contextlib import asynccontextmanager

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

from common.logger import logger
from data.database import PostgresDatabase
from data.database.models.mcp_servers import MCPServer


class MCPManager:
    """
    Manager for multiple MCP servers using langchain-mcp-adapters

    Handles connection pooling, lazy initialization, and workspace/user filtering.
    """

    def __init__(self, database: PostgresDatabase, workspace_id: UUID, user_id: UUID):
        """
        Initialize MCP Manager

        Args:
            database: Database instance
            workspace_id: Workspace ID to filter servers
            user_id: User ID to filter servers
        """
        self.database = database
        self.workspace_id = workspace_id
        self.user_id = user_id
        self._multi_client: Optional[MultiServerMCPClient] = None
        self._server_configs: Dict[str, MCPServer] = {}
        self._initialized = False

    async def initialize(self):
        """
        Load and connect to servers

        Servers are filtered by workspace_id and user_id.
        Only active servers are connected.
        """
        logger.info("Initializing MCP Manager...")

        servers = self._load_servers()
        if not servers:
            logger.warning("No servers found")
            return

        # Build connections config for MultiServerMCPClient
        connections = {}
        servers.sort(key=lambda s: s.priority, reverse=True)

        for server in servers:
            if server.mcp_config.get('is_active', False):
                try:
                    connection_config = self._build_connection_config(server)
                    connections[server.name] = connection_config
                    self._server_configs[server.name] = server
                except Exception as e:
                    logger.error(f"Failed to build config for {server.name}: {e}")

        # Create MultiServerMCPClient with all active servers
        if connections:
            self._multi_client = MultiServerMCPClient(connections=connections)
            self._initialized = True
        else:
            logger.warning("No active servers to initialize")

    def _load_servers(self) -> List[MCPServer]:
        """
        Load servers from database, filtered by workspace and user

        Returns:
            List of MCPServer instances
        """
        with self.database.get_session() as session:
            query = session.query(MCPServer)
            query = query.filter(
                MCPServer.workspace_id == self.workspace_id,
                MCPServer.user_id == self.user_id
            )
            return query.all()

    def _build_connection_config(self, server: MCPServer) -> Dict[str, Any]:
        """
        Build connection configuration for a server

        Args:
            server: MCPServer instance

        Returns:
            Connection configuration dict
        """
        transport_type = server.transport_type

        if transport_type == 'stdio':
            return {
                "command": server.command,
                "args": server.args or [],
                "env": server.env or {},
                "transport": "stdio"
            }
        elif transport_type == 'sse':
            config = {
                "url": server.url,
                "transport": "sse"
            }

            if server.headers:
                headers = server.headers.copy()
                if server.api_key and 'Authorization' not in headers:
                    headers['Authorization'] = f"Bearer {server.api_key}"
                config["headers"] = headers
            elif server.api_key:
                config["headers"] = {"Authorization": f"Bearer {server.api_key}"}

            return config
        elif transport_type == 'http' or transport_type == 'streamable_http':
            config = {
                "url": server.url,
                "transport": "streamable_http"
            }

            if server.headers:
                headers = server.headers.copy()
                if server.api_key and 'Authorization' not in headers:
                    headers['Authorization'] = f"Bearer {server.api_key}"
                config["headers"] = headers
            elif server.api_key:
                config["headers"] = {"Authorization": f"Bearer {server.api_key}"}

            return config
        else:
            raise ValueError(f"Unsupported transport type: {transport_type}")

    async def call_tool(self, server: str, tool: str, args: Dict = None) -> Optional[Dict]:
        """
        Call a tool on an MCP server

        Lazily initializes connections on first call if not already initialized.

        Args:
            server: Server name
            tool: Tool name
            args: Tool arguments

        Returns:
            Tool result as dict, or None if error
        """
        # Lazy initialization - connect on first use
        if not self._initialized:
            await self.initialize()

        if not self._multi_client or server not in self._server_configs:
            logger.warning(f"MCP server '{server}' not found or not connected")
            return None

        try:
            async with self._multi_client.session(server) as session:
                tools = await load_mcp_tools(session)

                # Find the tool by name
                target_tool = next((t for t in tools if t.name == tool), None)
                if not target_tool:
                    logger.error(f"Tool '{tool}' not found on server '{server}'")
                    return None

                # Invoke the tool
                result = await target_tool.ainvoke(args or {})

                # Return result as dict
                if isinstance(result, str):
                    return {"content": result, "isError": False}
                elif isinstance(result, dict):
                    return result
                else:
                    return {"content": str(result), "isError": False}

        except Exception as e:
            logger.error(f"call_tool error on {server}.{tool}: {e}", exc_info=True)
            return {"content": str(e), "isError": True}

    async def get_all_tools(self) -> Dict[str, List[Dict]]:
        """
        Get all tools from all connected servers

        Returns:
            Dict mapping server names to lists of tool definitions
        """
        if not self._initialized:
            await self.initialize()

        result = {}
        for server_name in self._server_configs.keys():
            try:
                async with self._multi_client.session(server_name) as session:
                    tools = await load_mcp_tools(session)
                    result[server_name] = [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "input_schema": tool.args_schema.schema() if hasattr(tool, 'args_schema') and tool.args_schema else {}
                        }
                        for tool in tools
                    ]
            except Exception as e:
                logger.error(f"Failed to get tools from {server_name}: {e}")
                result[server_name] = []

        return result

    async def read_resource(self, server: str, uri: str) -> Optional[Dict]:
        """
        Read a resource from an MCP server

        Args:
            server: Server name
            uri: Resource URI

        Returns:
            Resource content as dict, or None if error
        """
        if not self._initialized:
            await self.initialize()

        if not self._multi_client or server not in self._server_configs:
            logger.warning(f"MCP server '{server}' not found")
            return None

        try:
            async with self._multi_client.session(server) as session:
                if hasattr(session, '_session'):
                    result = await session._session.read_resource(uri)
                    return result.model_dump() if hasattr(result, 'model_dump') else None
                return None
        except Exception as e:
            logger.error(f"read_resource error: {e}")
            return None

    async def get_all_resources(self) -> Dict[str, List[Dict]]:
        """
        Get all resources from all connected servers

        Returns:
            Dict mapping server names to lists of resources
        """
        if not self._initialized:
            await self.initialize()

        result = {}
        for server_name in self._server_configs.keys():
            try:
                async with self._multi_client.session(server_name) as session:
                    if hasattr(session, '_session'):
                        res = await session._session.list_resources()
                        result[server_name] = [r.model_dump() for r in res.resources] if hasattr(res, 'resources') else []
                    else:
                        result[server_name] = []
            except Exception as e:
                logger.error(f"Failed to get resources from {server_name}: {e}")
                result[server_name] = []

        return result

    async def get_prompt(self, server: str, prompt: str, args: Dict = None) -> Optional[Dict]:
        """
        Get a prompt from an MCP server

        Args:
            server: Server name
            prompt: Prompt name
            args: Prompt arguments

        Returns:
            Prompt content as dict, or None if error
        """
        if not self._initialized:
            await self.initialize()

        if not self._multi_client or server not in self._server_configs:
            logger.warning(f"MCP server '{server}' not found")
            return None

        try:
            async with self._multi_client.session(server) as session:
                if hasattr(session, '_session'):
                    result = await session._session.get_prompt(prompt, arguments=args or {})
                    return result.model_dump() if hasattr(result, 'model_dump') else None
                return None
        except Exception as e:
            logger.error(f"get_prompt error: {e}")
            return None

    async def get_all_prompts(self) -> Dict[str, List[Dict]]:
        """
        Get all prompts from all connected servers

        Returns:
            Dict mapping server names to lists of prompts
        """
        if not self._initialized:
            await self.initialize()

        result = {}
        for server_name in self._server_configs.keys():
            try:
                async with self._multi_client.session(server_name) as session:
                    if hasattr(session, '_session'):
                        res = await session._session.list_prompts()
                        result[server_name] = [p.model_dump() for p in res.prompts] if hasattr(res, 'prompts') else []
                    else:
                        result[server_name] = []
            except Exception as e:
                logger.error(f"Failed to get prompts from {server_name}: {e}")
                result[server_name] = []

        return result

    def get_server_info(self, name: str) -> Optional[Dict]:
        """
        Get server information

        Args:
            name: Server name

        Returns:
            Server info dict, or None if not found
        """
        if name not in self._server_configs:
            return None

        server = self._server_configs[name]
        return {
            "name": server.name,
            "display_name": server.display_name,
            "transport": server.transport_type,
            "url": server.url if hasattr(server, 'url') else None,
            "connected": self._initialized,
        }

    def get_all_info(self) -> Dict[str, Dict]:
        """
        Get information for all servers

        Returns:
            Dict mapping server names to server info dicts
        """
        return {
            name: self.get_server_info(name)
            for name in self._server_configs.keys()
        }

    async def add_server(self, config: Dict[str, Any]) -> bool:
        """
        Add a new server dynamically

        Args:
            config: Server configuration dict. Must include 'workspace_id' and 'user_id'.

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.database.get_session() as session:
                server = MCPServer(**config)
                session.add(server)

                # Validate config before saving
                is_valid, error_msg = server.validate_config()
                if not is_valid:
                    logger.error(f"Invalid server config: {error_msg}")
                    return False

                session.commit()
                session.refresh(server)

                # Re-initialize to include new server
                if server.mcp_config.get('is_active', False):
                    await self.initialize()

                return True
        except Exception as e:
            logger.error(f"Add server failed: {e}", exc_info=True)
            return False

    async def remove_server(self, name: str) -> bool:
        """
        Remove a server

        Args:
            name: Server name

        Returns:
            True if successful, False otherwise
        """
        try:
            # Remove from configs
            if name in self._server_configs:
                del self._server_configs[name]

            # Remove from database
            with self.database.get_session() as session:
                servers = session.query(MCPServer).filter(
                    MCPServer.workspace_id == self.workspace_id,
                    MCPServer.user_id == self.user_id
                ).all()

                for server in servers:
                    if server.name == name:
                        session.delete(server)
                        session.commit()

                        # Re-initialize to remove from multi-client
                        await self.initialize()
                        return True

            return False
        except Exception as e:
            logger.error(f"Remove server failed: {e}", exc_info=True)
            return False

    async def shutdown(self):
        """
        Disconnect all servers and cleanup

        Note: langchain-mcp-adapters handles cleanup automatically via context managers
        """
        logger.info("Shutting down MCP Manager...")

        try:
            # Clear references
            self._multi_client = None
            self._server_configs.clear()
            self._initialized = False

            logger.info("✓ Shutdown complete")
        except Exception as e:
            logger.error(f"Shutdown error: {e}")
            self._multi_client = None
            self._server_configs.clear()
            self._initialized = False


@asynccontextmanager
async def create_manager(database: PostgresDatabase, workspace_id: Optional[UUID] = None, user_id: Optional[UUID] = None):
    """
    Context manager for MCP manager

    Args:
        database: Database instance
        workspace_id: Optional workspace ID to filter servers
        user_id: Optional user ID to filter servers

    Usage:
        async with create_manager(db, workspace_id, user_id) as manager:
            tools = await manager.get_all_tools()

    Yields:
        Initialized MCPManager instance
    """
    manager = MCPManager(database, workspace_id, user_id)
    try:
        await manager.initialize()
        yield manager
    finally:
        await manager.shutdown()
