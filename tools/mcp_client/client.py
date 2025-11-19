"""MCP Client using langchain-mcp-adapters"""

from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

from common.logger import logger
from .utils import MCPConnection, build_connection_config


class MCPClient:
    def __init__(self, server: MCPConnection):
        self.server = server
        self._multi_client: Optional[MultiServerMCPClient] = None
        self._session = None
        self._session_ctx = None
        self._connected = False

    async def connect(self) -> bool:
        try:
            logger.info(f"Connecting: {self.server.name}")

            self._multi_client = MultiServerMCPClient(
                connections={self.server.name: build_connection_config(self.server)}
            )

            self._session_ctx = self._multi_client.session(self.server.name)
            self._session = await self._session_ctx.__aenter__()

            self._connected = True
            logger.info(f"Connected: {self.server.name}")
            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}", exc_info=True)
            self._connected = False
            return False

    async def list_tools(self) -> List[Dict[str, Any]]:
        if not self._session:
            logger.warning("No active session")
            return []

        try:
            tools = await load_mcp_tools(self._session)
            result = []
            for tool in tools:
                tool_dict = {"name": tool.name, "description": tool.description}

                if hasattr(tool, 'args_schema') and tool.args_schema:
                    if hasattr(tool.args_schema, 'schema'):
                        tool_dict["input_schema"] = tool.args_schema.schema()
                    elif isinstance(tool.args_schema, dict):
                        tool_dict["input_schema"] = tool.args_schema
                    else:
                        tool_dict["input_schema"] = {}
                else:
                    tool_dict["input_schema"] = {}

                result.append(tool_dict)
            return result
        except Exception as e:
            logger.error(f"list_tools error: {e}", exc_info=True)
            return []

    async def call_tool(self, name: str, args: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        if not self._session:
            logger.warning("No active session")
            return None

        try:
            tools = await load_mcp_tools(self._session)
            tool = next((t for t in tools if t.name == name), None)

            if not tool:
                logger.error(f"Tool '{name}' not found")
                return None

            result = await tool.ainvoke(args or {})

            if isinstance(result, str):
                return {"content": result, "isError": False}
            elif isinstance(result, dict):
                return result
            else:
                return {"content": str(result), "isError": False}
        except Exception as e:
            logger.error(f"call_tool error: {e}", exc_info=True)
            return {"content": str(e), "isError": True}

    async def list_resources(self) -> List[Dict[str, Any]]:
        if not self._session:
            return []
        try:
            if hasattr(self._session, '_session'):
                result = await self._session._session.list_resources()
                return [r.model_dump() for r in result.resources] if hasattr(result, 'resources') else []
            return []
        except Exception as e:
            logger.error(f"list_resources error: {e}", exc_info=True)
            return []

    async def read_resource(self, uri: str) -> Optional[Dict[str, Any]]:
        if not self._session:
            return None
        try:
            if hasattr(self._session, '_session'):
                result = await self._session._session.read_resource(uri)
                return result.model_dump() if hasattr(result, 'model_dump') else None
            return None
        except Exception as e:
            logger.error(f"read_resource error: {e}", exc_info=True)
            return None

    async def list_prompts(self) -> List[Dict[str, Any]]:
        if not self._session:
            return []
        try:
            if hasattr(self._session, '_session'):
                result = await self._session._session.list_prompts()
                return [p.model_dump() for p in result.prompts] if hasattr(result, 'prompts') else []
            return []
        except Exception as e:
            logger.error(f"list_prompts error: {e}", exc_info=True)
            return []

    async def get_prompt(self, name: str, args: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        if not self._session:
            return None
        try:
            if hasattr(self._session, '_session'):
                result = await self._session._session.get_prompt(name, arguments=args or {})
                return result.model_dump() if hasattr(result, 'model_dump') else None
            return None
        except Exception as e:
            logger.error(f"get_prompt error: {e}", exc_info=True)
            return None

    async def disconnect(self):
        try:
            if self._session_ctx:
                await self._session_ctx.__aexit__(None, None, None)
                self._session_ctx = None
                self._session = None

            self._multi_client = None
            self._connected = False
            logger.info(f"Disconnected: {self.server.name}")
        except Exception as e:
            logger.error(f"Disconnect error: {e}")
            self._session_ctx = None
            self._session = None
            self._multi_client = None
            self._connected = False

    async def is_connected(self) -> bool:
        if not self._connected or not self._session:
            return False
        try:
            await load_mcp_tools(self._session)
            return True
        except Exception:
            self._connected = False
            return False

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.server.name,
            "display_name": self.server.display_name,
            "connected": self._connected,
            "transport": self.server.transport_type,
            "url": self.server.url if hasattr(self.server, 'url') else None,
        }


@asynccontextmanager
async def create_client(server: MCPConnection):
    client = MCPClient(server)
    try:
        if await client.connect():
            yield client
        else:
            raise RuntimeError(f"Failed to connect: {server.name}")
    finally:
        await client.disconnect()
