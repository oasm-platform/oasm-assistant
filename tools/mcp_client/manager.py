from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

from common.logger import logger
from data.database import postgres_db, PostgresDatabase
from data.database.models.mcp_servers import MCPServer
from tools.mcp_client.client import MCPClient


class MCPManager:
    """Manager for multiple MCP servers"""

    def __init__(self, database: PostgresDatabase):
        self.database = database
        self.clients: Dict[str, MCPClient] = {}

    async def initialize(self):
        """Load and connect to servers"""
        logger.info("Initializing MCP Manager...")

        servers = self._load_servers()
        if not servers:
            logger.warning("No servers found")
            return

        # Connect by priority
        servers.sort(key=lambda s: s.priority, reverse=True)
        for server in servers:
            if server.is_active:
                await self._connect(server)

        logger.info(f"✓ Connected {len(self.clients)} servers")

    def _load_servers(self) -> List[MCPServer]:
        """Load servers from database"""
        with self.database.get_session() as session:
            return session.query(MCPServer).all()

    async def _connect(self, server: MCPServer):
        """Connect to a server"""
        try:
            client = MCPClient(server)
            if await client.connect():
                self.clients[server.name] = client
                logger.info(f"Connected to {server.name}")
            else:
                logger.error(f"Failed to connect to {server.name}")
        except Exception as e:
            logger.error(f"Connect failed {server.name}: {e}")

    async def call_tool(self, server: str, tool: str, args: Dict = None) -> Optional[Dict]:
        """Call a tool"""
        client = self.clients.get(server)
        if not client or not client.is_connected():
            return None
        return await client.call_tool(tool, args)

    async def get_all_tools(self) -> Dict[str, List[Dict]]:
        result = {}
        for name, client in self.clients.items():
            try:
                result[name] = await client.list_tools()
            except Exception as e:
                logger.error(f"Failed to get tools from {name}: {e}")
                result[name] = []
        return result

    async def read_resource(self, server: str, uri: str) -> Optional[Dict]:
        """Read a resource"""
        client = self.clients.get(server)
        return await client.read_resource(uri) if client else None

    async def get_all_resources(self) -> Dict[str, List[Dict]]:
        """Get all resources"""
        return {name: await client.list_resources() for name, client in self.clients.items()}

    async def get_prompt(self, server: str, prompt: str, args: Dict = None) -> Optional[Dict]:
        """Get a prompt"""
        client = self.clients.get(server)
        return await client.get_prompt(prompt, args) if client else None

    async def get_all_prompts(self) -> Dict[str, List[Dict]]:
        """Get all prompts"""
        return {name: await client.list_prompts() for name, client in self.clients.items()}

    def get_server_info(self, name: str) -> Optional[Dict]:
        """Get server info"""
        client = self.clients.get(name)
        return client.get_info() if client else None

    def get_all_info(self) -> Dict[str, Dict]:
        """Get all server info"""
        return {name: client.get_info() for name, client in self.clients.items()}

    async def add_server(self, config: Dict[str, Any]) -> bool:
        """Add a new server"""
        try:
            with self.database.get_session() as session:
                server = MCPServer(**config)
                session.add(server)
                session.commit()
                session.refresh(server)

                if server.is_active:
                    await self._connect(server)
                return True
        except Exception as e:
            logger.error(f"Add server failed: {e}")
            return False

    async def remove_server(self, name: str) -> bool:
        """Remove a server"""
        try:
            if name in self.clients:
                await self.clients[name].disconnect()
                del self.clients[name]

            with self.database.get_session() as session:
                server = session.query(MCPServer).filter(MCPServer.name == name).first()
                if server:
                    session.delete(server)
                    session.commit()
                    return True
            return False
        except Exception as e:
            logger.error(f"Remove server failed: {e}")
            return False

    async def shutdown(self):
        """Disconnect all servers"""
        logger.info("Shutting down...")
        for client in self.clients.values():
            try:
                await client.disconnect()
            except Exception as e:
                logger.error(f"Disconnect error: {e}")
        self.clients.clear()
        logger.info("✓ Shutdown complete")


@asynccontextmanager
async def create_manager(database: PostgresDatabase):
    """
    Context manager for MCP manager

    Usage:
        async with create_manager(db) as manager:
            tools = await manager.get_all_tools()
    """
    manager = MCPManager(database)
    try:
        await manager.initialize()
        yield manager
    finally:
        await manager.shutdown()
