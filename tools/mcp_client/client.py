from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client

from common.logger import logger
from data.database.models.mcp_servers import MCPServer, TransportType


class MCPClient:
    """
    MCP Client using official mcp library

    Simplified implementation that delegates protocol handling to the SDK.
    """

    def __init__(self, server: MCPServer):
        self.server = server
        self.session: Optional[ClientSession] = None
        self._context = None
        self._read = None
        self._write = None

    async def connect(self) -> bool:
        """Connect to MCP server"""
        try:
            logger.info(f"Connecting: {self.server.name}")

            # Create transport context
            if self.server.transport_type == TransportType.STDIO:
                params = StdioServerParameters(
                    command=self.server.command,
                    args=self.server.args or [],
                    env=self.server.env
                )
                self._context = stdio_client(params)
            else:  # SSE
                self._context = sse_client(
                    url=self.server.url,
                    headers=self.server.headers or {}
                )

            # Connect
            self._read, self._write = await self._context.__aenter__()
            self.session = ClientSession(self._read, self._write)
            await self.session.__aenter__()
            await self.session.initialize()

            logger.info(f"✓ Connected: {self.server.name}")
            return True

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools"""
        if not self.session:
            return []
        try:
            result = await self.session.list_tools()
            return [t.model_dump() for t in result.tools]
        except Exception as e:
            logger.error(f"list_tools error: {e}")
            return []

    async def call_tool(self, name: str, args: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """Call a tool"""
        if not self.session:
            return None
        try:
            result = await self.session.call_tool(name, arguments=args or {})
            return result.model_dump()
        except Exception as e:
            logger.error(f"call_tool error: {e}")
            return None

    async def list_resources(self) -> List[Dict[str, Any]]:
        """List available resources"""
        if not self.session:
            return []
        try:
            result = await self.session.list_resources()
            return [r.model_dump() for r in result.resources]
        except Exception as e:
            logger.error(f"list_resources error: {e}")
            return []

    async def read_resource(self, uri: str) -> Optional[Dict[str, Any]]:
        """Read a resource"""
        if not self.session:
            return None
        try:
            result = await self.session.read_resource(uri)
            return result.model_dump()
        except Exception as e:
            logger.error(f"read_resource error: {e}")
            return None

    async def list_prompts(self) -> List[Dict[str, Any]]:
        """List available prompts"""
        if not self.session:
            return []
        try:
            result = await self.session.list_prompts()
            return [p.model_dump() for p in result.prompts]
        except Exception as e:
            logger.error(f"list_prompts error: {e}")
            return []

    async def get_prompt(self, name: str, args: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """Get a prompt"""
        if not self.session:
            return None
        try:
            result = await self.session.get_prompt(name, arguments=args or {})
            return result.model_dump()
        except Exception as e:
            logger.error(f"get_prompt error: {e}")
            return None

    async def disconnect(self):
        """Disconnect from server"""
        try:
            if self.session:
                await self.session.__aexit__(None, None, None)
            if self._context:
                await self._context.__aexit__(None, None, None)
            logger.info(f"Disconnected: {self.server.name}")
        except Exception as e:
            logger.error(f"Disconnect error: {e}")

    def is_connected(self) -> bool:
        """Check connection status"""
        return self.session is not None

    def get_info(self) -> Dict[str, Any]:
        """Get client info"""
        return {
            "name": self.server.name,
            "connected": self.is_connected(),
            "transport": self.server.transport_type.value,
        }


@asynccontextmanager
async def create_client(server: MCPServer):
    """
    Context manager for MCP client

    Usage:
        async with create_client(server) as client:
            tools = await client.list_tools()
    """
    client = MCPClient(server)
    try:
        if await client.connect():
            yield client
        else:
            raise RuntimeError(f"Failed to connect: {server.name}")
    finally:
        await client.disconnect()
