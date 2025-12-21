"""
MCP Manager using langchain-mcp-adapters

This module provides a manager for handling multiple MCP server connections.
"""

from typing import Dict, List, Optional, Any
from uuid import UUID
from contextlib import asynccontextmanager
import warnings
import logging
import asyncio
import nest_asyncio
from common.config import configs

# Enable nested asyncio for MCP calls within event loop
nest_asyncio.apply()

# Suppress pydantic validation warnings from MCP notification parsing
warnings.filterwarnings("ignore", message="Failed to validate notification")
# Also suppress at root logger level for MCP-related warnings
logging.getLogger("root").addFilter(lambda record: "Failed to validate notification" not in record.getMessage())

from langchain_mcp_adapters.client import MultiServerMCPClient

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

            all_connections = []
            
            # Load from DB if exists
            if mcp_config:
                all_connections = mcp_config_to_connections(mcp_config)
                # Filter disabled ones
                all_connections = [
                    conn for conn in all_connections
                    if not mcp_config.is_server_disabled(conn.name)
                ]
            
            # Define default servers
            default_servers = [
                MCPConnection(
                    name="oasm-assistant-mcp",
                    workspace_id=self.workspace_id,
                    user_id=self.user_id,
                    transport_type="sse",
                    url=configs.oasm_core_api_url + "/api/mcp",
                    headers={"api-key": configs.oasm_cloud_apikey}
                ),
                MCPConnection(
                    name="searxng",
                    workspace_id=self.workspace_id,
                    user_id=self.user_id,
                    transport_type="stdio",
                    command="npx",
                    args=["-y", "mcp-searxng"],
                    env={"SEARXNG_URL": configs.searxng_url}
                )
            ]

            # Add default servers if not present (DB overrides defaults if same name exists)
            existing_names = {conn.name for conn in all_connections}
            
            for server in default_servers:
                if server.name not in existing_names:
                    # Check if disabled in DB config
                    if mcp_config and mcp_config.is_server_disabled(server.name):
                        continue
                        
                    all_connections.append(server)
                    
            return all_connections

    def _get_server_timeout(self, server_name: str) -> int:
        """Get timeout for a server from database config, default 60 seconds"""
        with self.database.get_session() as session:
            mcp_config = session.query(MCPConfig).filter(
                MCPConfig.workspace_id == self.workspace_id,
                MCPConfig.user_id == self.user_id
            ).first()
            
            if mcp_config:
                return mcp_config.get_timeout(server_name)
            return 60
    
    def _get_allowed_tools(self, server_name: str) -> Optional[List[str]]:
        """Get allowed tools for a server from database config. None means all tools allowed"""
        with self.database.get_session() as session:
            mcp_config = session.query(MCPConfig).filter(
                MCPConfig.workspace_id == self.workspace_id,
                MCPConfig.user_id == self.user_id
            ).first()
            
            if mcp_config:
                return mcp_config.get_allowed_tools(server_name)
            return None

    async def get_server_status(self, server_name: str, test_connection: bool = False) -> tuple[bool, Optional[str]]:
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
        if test_connection:
            try:
                # Test by trying to list tools from the server
                # This will fail if the server is down
                async with self._multi_client.session(server_name) as session:
                    # Make a direct call to the session to check server status with timeout
                    # This should force an actual connection attempt
                    tools_result = await asyncio.wait_for(session.list_tools(), timeout=5.0)
                    # Verify we got a valid response
                    if tools_result and hasattr(tools_result, 'tools'):
                        return (True, None)
                    else:
                        return (False, "Server returned invalid response")
            except asyncio.TimeoutError:
                return (False, "Server response timeout")
            except Exception as e:
                return (False, f"Server not responding: {str(e)}")

        return (True, None)



    async def call_tool(self, server: str, tool: str, args: Dict = None) -> Optional[Dict]:
        """
        Call a tool on an MCP server using native MCP protocol

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
            logger.debug(f"Opening session for server: {server}")
            async with self._multi_client.session(server) as session:
                logger.debug(f"Calling tool: {tool} with args: {args}")
                # Use native MCP protocol call_tool instead of LangChain adapter
                result = await session.call_tool(tool, args or {})
                logger.debug(f"Tool call result type: {type(result)}")

                # MCP returns CallToolResult with content array
                if hasattr(result, 'content') and result.content:
                    logger.debug(f"Result has content array with {len(result.content)} items")
                    # Extract first content item
                    first_content = result.content[0]

                    # Check if it's a text content
                    if hasattr(first_content, 'text'):
                        # Try to parse as JSON
                        import json
                        try:
                            data = json.loads(first_content.text)
                            logger.debug(f"Parsed JSON data successfully")
                            return data if isinstance(data, dict) else {"content": first_content.text, "isError": False}
                        except json.JSONDecodeError:
                            logger.debug(f"Content is not JSON, returning as text")
                            return {"content": first_content.text, "isError": False}
                    else:
                        return {"content": str(first_content), "isError": False}

                return {"content": str(result), "isError": False}

        except Exception as e:
            import traceback
            logger.error(f"call_tool error on {server}.{tool}: {e}", exc_info=True)
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            return {"content": str(e), "isError": True}

    async def call_tool_with_timeout(self, server: str, tool: str, args: Dict = None, timeout: int = None) -> Optional[Dict]:
        """
        Call a tool on an MCP server with custom timeout
        
        Args:
            server: Server name
            tool: Tool name
            args: Tool arguments
            timeout: Custom timeout in seconds, if None uses server's configured timeout
        
        Returns:
            Tool result as dict, or None if error
        """        
        if timeout is None:
            timeout = self._get_server_timeout(server)
        
        try:
            return await asyncio.wait_for(
                self.call_tool(server, tool, args),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"Tool call timeout after {timeout}s: {server}.{tool}")
            return {"content": f"Tool call timeout after {timeout} seconds", "isError": True}
        except Exception as e:
            logger.error(f"call_tool_with_timeout error: {e}", exc_info=True)
            return {"content": str(e), "isError": True}

    async def get_tools(self, server_name: str, apply_filter: bool = True) -> List[Dict]:
        """
        Get tools for a specific server
        Args:
            server_name: Server name
            apply_filter: Whether to filter tools based on allowed_tools config (default: True)
        Returns:
            List of tool definitions
        """
        if not self._initialized:
            await self.initialize()

        if not self._multi_client or server_name not in self._server_configs:
            logger.warning(f"MCP server '{server_name}' not found or not connected")
            return []

        try:
            async with self._multi_client.session(server_name) as session:
                tools_result = await session.list_tools()
                all_tools = [
                    {
                        "name": tool.name,
                        "description": tool.description or "No description",
                        "input_schema": tool.inputSchema if hasattr(tool, 'inputSchema') else {}
                    }
                    for tool in tools_result.tools
                ]
                
                if apply_filter:
                    # Filter by allowed_tools if configured
                    allowed_tools = self._get_allowed_tools(server_name)
                    if allowed_tools is not None:
                        all_tools = [t for t in all_tools if t["name"] in allowed_tools]
                
                return all_tools
        except Exception as e:
            logger.error(f"Failed to get tools from {server_name}: {e}", exc_info=True)
            return []

    async def get_all_tools(self) -> Dict[str, List[Dict]]:
        """
        Get all tools from all connected servers using native MCP protocol

        Returns:
            Dict mapping server names to lists of tool definitions
        """
        if not self._initialized:
            await self.initialize()

        result = {}
        for server_name in self._server_configs.keys():
            result[server_name] = await self.get_tools(server_name)

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

    async def get_resources(self, server_name: str) -> List[Dict]:
        """
        Get resources for a specific server
        Args:
            server_name: Server name
        Returns:
            List of resources
        """
        if not self._initialized:
            await self.initialize()

        if not self._multi_client or server_name not in self._server_configs:
            return []

        try:
            async with self._multi_client.session(server_name) as session:
                if hasattr(session, '_session'):
                    res = await session._session.list_resources()
                    return [r.model_dump() for r in res.resources] if hasattr(res, 'resources') else []
                return []
        except Exception as e:
            logger.error(f"Failed to get resources from {server_name}: {e}")
            return []

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
            result[server_name] = await self.get_resources(server_name)

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
