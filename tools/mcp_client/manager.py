"""
MCP Manager using langchain-mcp-adapters

This module provides a manager for handling multiple MCP server connections.
"""

from typing import Dict, List, Optional, Any
from uuid import UUID
from contextlib import asynccontextmanager
import warnings
import logging

# Suppress pydantic validation warnings from MCP notification parsing
warnings.filterwarnings("ignore", message="Failed to validate notification")
# Also suppress at root logger level for MCP-related warnings
logging.getLogger("root").addFilter(lambda record: "Failed to validate notification" not in record.getMessage())

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

from common.logger import logger
from data.database import PostgresDatabase
from data.database.models import MCPConfig
from .utils import MCPConnection, mcp_config_to_connections, build_connection_config


class MCPManager:
    """
    Manager for multiple MCP servers using langchain-mcp-adapters

    Handles connection pooling, lazy initialization, and workspace/user filtering.
    """

    def __init__(self, database: PostgresDatabase, workspace_id: UUID, user_id: UUID, async_loop=None):
        """
        Initialize MCP Manager

        Args:
            database: Database instance
            workspace_id: Workspace ID to filter servers
            user_id: User ID to filter servers
            async_loop: Optional event loop for async operations
        """
        self.database = database
        self.workspace_id = workspace_id
        self.user_id = user_id
        self._multi_client: Optional[MultiServerMCPClient] = None
        self._server_configs: Dict[str, MCPConnection] = {}
        self._failed_servers: Dict[str, str] = {}  # Track failed connection attempts
        self._initialized = False
        self._async_loop = async_loop  # Event loop for testing connections

    async def initialize(self):
        """Load MCP config and connect to servers"""
        # Clear previous state
        self._server_configs.clear()
        self._failed_servers.clear()
        self._multi_client = None
        self._initialized = False

        servers = self._load_servers()
        if not servers:
            logger.warning("No servers found")
            return

        # Build connections config
        connections = {}
        for server in servers:
            try:
                connection_config = build_connection_config(server)
                connections[server.name] = connection_config
                self._server_configs[server.name] = server
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Failed to build config for {server.name}: {error_msg}")
                # Track as failed server
                self._failed_servers[server.name] = error_msg

        if connections:
            try:
                self._multi_client = MultiServerMCPClient(connections=connections)
                self._initialized = True
            except Exception as e:
                logger.error(f"Failed to initialize MultiServerMCPClient: {e}")
                # Mark all servers as failed if client creation fails
                for server_name in connections.keys():
                    self._failed_servers[server_name] = f"Client init failed: {e}"
                self._initialized = True  # Still mark as initialized to track failures
        else:
            logger.warning("No active servers to initialize")
            self._initialized = True  # Mark as initialized even with no servers

    def _load_servers(self) -> List[MCPConnection]:
        """Load MCP config from database and convert to connections (only enabled/not disabled servers)"""
        with self.database.get_session() as session:
            mcp_config = session.query(MCPConfig).filter(
                MCPConfig.workspace_id == self.workspace_id,
                MCPConfig.user_id == self.user_id
            ).first()

            if mcp_config:
                # Only load servers that are not disabled
                all_connections = mcp_config_to_connections(mcp_config)
                enabled_connections = [
                    conn for conn in all_connections
                    if not mcp_config.is_server_disabled(conn.name)
                ]
                return enabled_connections
            return []

    def get_server_status(self, server_name: str, test_connection: bool = False) -> tuple[bool, Optional[str]]:
        """
        Get connection status for a specific server

        Args:
            server_name: Name of the server to check
            test_connection: If True, will attempt to actually test the connection (slower but accurate)

        Returns:
            tuple: (is_active: bool, error_message: Optional[str])
            - (True, None) - Server connected and operational
            - (False, "error message") - Server failed with error or disabled
        """
        # Check if server exists and is disabled in database
        with self.database.get_session() as session:
            mcp_config = session.query(MCPConfig).filter(
                MCPConfig.workspace_id == self.workspace_id,
                MCPConfig.user_id == self.user_id
            ).first()

            if not mcp_config:
                return (False, "MCP config not found")

            # Check if server exists in config
            if server_name not in mcp_config.servers:
                return (False, "Server not found in config")

            # Check disabled flag - if disabled, return error
            if mcp_config.is_server_disabled(server_name):
                return (False, "Server is disabled")

        # Server is enabled, now check connection status
        if not self._initialized:
            return (False, "Manager not initialized")

        # Check if server failed during initialization
        if server_name in self._failed_servers:
            error_msg = self._failed_servers.get(server_name, "Connection failed")
            return (False, error_msg)

        # Check if server is in loaded configs
        if server_name not in self._server_configs:
            return (False, "Server not loaded")

        # Check if multi_client exists
        if not self._multi_client:
            return (False, "MCP client not initialized")

        # If test_connection is requested, actually try to use the connection
        if test_connection and self._async_loop:
            try:
                # Test by trying to list tools from the server
                # This will fail if the server is down
                import asyncio

                async def test_server():
                    async with self._multi_client.session(server_name) as session:
                        tools = await load_mcp_tools(session)
                        return tools

                future = asyncio.run_coroutine_threadsafe(
                    test_server(),
                    self._async_loop
                )
                # Wait for result with reasonable timeout
                future.result(timeout=10)
                return (True, None)
            except TimeoutError:
                return (False, "Server response timeout")
            except Exception as e:
                return (False, f"Server not responding: {str(e)}")

        # Without test_connection, assume server is active if:
        # - It's not disabled
        # - Manager is initialized
        # - Server is in loaded configs
        # - Multi-client exists
        # - Server didn't fail during initialization
        return (True, None)



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

    async def add_server(self, name: str, server_config: Dict[str, Any]) -> bool:
        """
        Add a new server to MCPConfig

        Args:
            name: Server name
            server_config: Server configuration dict (transport_type, url/command, etc.)

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.database.get_session() as session:
                # Get or create MCPConfig
                mcp_config = session.query(MCPConfig).filter(
                    MCPConfig.workspace_id == self.workspace_id,
                    MCPConfig.user_id == self.user_id
                ).first()

                if not mcp_config:
                    mcp_config = MCPConfig(
                        workspace_id=self.workspace_id,
                        user_id=self.user_id,
                        config_json={"mcpServers": {}}
                    )
                    session.add(mcp_config)

                # Add server to JSON
                mcp_config.add_server(name, server_config)
                session.commit()

                # Re-initialize to include new server
                await self.initialize()
                return True

        except Exception as e:
            logger.error(f"Add server failed: {e}", exc_info=True)
            return False

    async def remove_server(self, name: str) -> bool:
        """
        Remove a server from MCPConfig

        Args:
            name: Server name

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.database.get_session() as session:
                mcp_config = session.query(MCPConfig).filter(
                    MCPConfig.workspace_id == self.workspace_id,
                    MCPConfig.user_id == self.user_id
                ).first()

                if not mcp_config or name not in mcp_config.servers:
                    logger.warning(f"Server '{name}' not found in config")
                    return False

                # Remove server from JSON
                mcp_config.remove_server(name)
                session.commit()

                # Re-initialize to remove from multi-client
                await self.initialize()
                return True

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
