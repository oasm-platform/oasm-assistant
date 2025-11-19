from app.protos import assistant_pb2, assistant_pb2_grpc
from data.database import postgres_db
from data.database.models import MCPConfig
from tools.mcp_client import MCPManager
from common.logger import logger
from common.config import configs
from grpc import StatusCode
from app.interceptors import get_metadata_interceptor
from uuid import UUID
from google.protobuf.json_format import MessageToDict
from google.protobuf.struct_pb2 import Struct
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor


class MCPServerService(assistant_pb2_grpc.MCPServerServiceServicer):
    """MCP Server Service - manages MCPConfig (JSON with multiple servers)"""

    def __init__(self):
        self.db = postgres_db
        self._managers = {}  # Cache managers by (workspace_id, user_id)
        self._manager_lock = threading.Lock()
        self._async_loop = None
        self._async_thread = None
        self._executor = ThreadPoolExecutor(max_workers=5)
        self.mcp_timeout = configs.mcp_timeout
        self._setup_async_loop()

    def _setup_async_loop(self):
        """Setup dedicated event loop for async operations"""
        def run_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()

        self._async_loop = asyncio.new_event_loop()
        self._async_thread = threading.Thread(target=run_loop, args=(self._async_loop,), daemon=True)
        self._async_thread.start()

    def _run_async(self, coro):
        """Run async coroutine and wait for result"""
        future = asyncio.run_coroutine_threadsafe(coro, self._async_loop)
        return future.result(timeout=self.mcp_timeout)

    def _get_manager(self, workspace_id: UUID, user_id: UUID) -> MCPManager:
        """Get or create MCPManager (thread-safe)"""
        key = (str(workspace_id), str(user_id))

        if key not in self._managers:
            with self._manager_lock:
                if key not in self._managers:
                    # Pass the async loop to the manager for testing connections
                    self._managers[key] = MCPManager(self.db, workspace_id, user_id, self._async_loop)

        return self._managers[key]

    async def _handle_service_error(self, context, e: Exception, default_message: str, response_class):
        """Common error handling"""
        if isinstance(e, ValueError):
            logger.error(f"Invalid input: {e}")
            context.set_code(StatusCode.INVALID_ARGUMENT)
            context.set_details(str(e))
        else:
            logger.error(f"{default_message}: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
        return response_class(success=False)

    def _get_or_create_config(self, session, workspace_id: UUID, user_id: UUID) -> MCPConfig:
        """Get or create MCPConfig for workspace/user"""
        config = session.query(MCPConfig).filter(
            MCPConfig.workspace_id == workspace_id,
            MCPConfig.user_id == user_id
        ).first()

        if not config:
            config = MCPConfig(
                workspace_id=workspace_id,
                user_id=user_id,
                config_json={"mcpServers": {}}
            )
            session.add(config)
            session.flush()

        return config

    def _get_server_status(self, manager: MCPManager, server_name: str, test_connection: bool = True) -> tuple:
        """
        Get actual server status by checking manager state

        Args:
            manager: MCPManager instance
            server_name: Name of server to check
            test_connection: If True, actually test the connection (slower but accurate)

        Returns:
            tuple: (is_active: bool, error_message: Optional[str])
        """
        return manager.get_server_status(server_name, test_connection=test_connection)

    def _server_to_proto(self, name: str, server_config: dict, is_active: bool, error: str = None) -> assistant_pb2.MCPServer:
        """
        Convert server config dict to protobuf

        Args:
            name: Server name
            server_config: Server configuration dict
            is_active: True if server is connected and operational
            error: Error message if server failed or is disabled
        """
        # Build config with server name embedded in Claude Desktop format
        full_config = {name: server_config}

        # Create Struct and populate with dict
        config_struct = Struct()
        config_struct.update(full_config)

        # Create MCPServer with config and status (oneof: active or error)
        if is_active:
            proto_server = assistant_pb2.MCPServer(
                config=config_struct,
                active=True
            )
        else:
            proto_server = assistant_pb2.MCPServer(
                config=config_struct,
                error=error or "Unknown error"
            )
        return proto_server

    def cleanup(self):
        """Cleanup resources"""
        try:
            for manager in self._managers.values():
                try:
                    self._run_async(manager.shutdown())
                except Exception as e:
                    logger.error(f"Error shutting down manager: {e}")

            if self._async_loop and self._async_loop.is_running():
                self._async_loop.call_soon_threadsafe(self._async_loop.stop)

            if self._executor:
                self._executor.shutdown(wait=True)

            logger.info("MCPServerService cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    @get_metadata_interceptor
    async def AddMCPServers(self, request, context):
        """Add one or more servers to MCPConfig"""
        try:
            workspace_id = UUID(context.workspace_id)
            user_id = UUID(context.user_id)

            # Convert Struct to dict - expect {"mcpServers": {"name": {...}}}
            # Note: MessageToDict may return nested dicts with camelCase keys by default
            request_data = MessageToDict(
                request.mcp_config,
                preserving_proto_field_name=True
            )

            # Extract mcpServers - handle both camelCase and snake_case
            mcp_servers = request_data.get('mcpServers') or request_data.get('mcp_servers', {})
            if not mcp_servers:
                context.set_code(StatusCode.INVALID_ARGUMENT)
                msg = "Request must contain 'mcpServers' field with at least one server"
                context.set_details(msg)
                return assistant_pb2.AddMCPServersResponse(success=False)

            added_servers = []
            errors = []

            with self.db.get_session() as session:
                config = self._get_or_create_config(session, workspace_id, user_id)

                for server_name, server_config in mcp_servers.items():
                    try:
                        # Validate transport config
                        if 'url' not in server_config and 'command' not in server_config:
                            errors.append(f"{server_name}: must have 'url' or 'command'")
                            continue

                        # Check if server exists
                        if server_name in config.servers:
                            errors.append(f"{server_name}: already exists")
                            continue

                        # Add server
                        config.add_server(server_name, server_config)
                        # Store name for later status check
                        added_servers.append(server_name)

                    except Exception as e:
                        errors.append(f"{server_name}: {str(e)}")

                if added_servers:
                    session.commit()
                    # Refresh config to get latest state after commit
                    session.refresh(config)

                    # Reinitialize manager
                    manager = self._get_manager(workspace_id, user_id)
                    try:
                        self._run_async(manager.initialize())
                    except Exception as e:
                        logger.warning(f"Manager reinit failed: {e}")

                    # Build proto servers with actual connection status
                    proto_servers = []
                    for server_name in added_servers:
                        try:
                            server_config = config.servers.get(server_name)
                            if server_config:
                                is_active, error = self._get_server_status(manager, server_name)
                                proto_servers.append(self._server_to_proto(server_name, server_config, is_active, error))
                            else:
                                logger.warning(f"Server config not found for: {server_name}")
                        except Exception as e:
                            logger.error(f"Error building proto for {server_name}: {e}", exc_info=True)
                else:
                    proto_servers = []

                return assistant_pb2.AddMCPServersResponse(
                    servers=proto_servers,
                    success=len(added_servers) > 0
                )

        except Exception as e:
            return await self._handle_service_error(context, e, "Error adding servers", assistant_pb2.AddMCPServersResponse)

    @get_metadata_interceptor
    async def GetMCPServers(self, request, context):
        """Get all servers from MCPConfig"""
        try:
            workspace_id = UUID(context.workspace_id)
            user_id = UUID(context.user_id)

            with self.db.get_session() as session:
                config = self._get_or_create_config(session, workspace_id, user_id)

                # Get manager and check connection status
                manager = self._get_manager(workspace_id, user_id)

                if not manager._initialized:
                    try:
                        self._run_async(manager.initialize())
                    except Exception as e:
                        logger.error(f"Failed to initialize manager: {e}")

                # Build response with connection status
                proto_servers = []
                for name, server_config in config.servers.items():
                    is_active, error = self._get_server_status(manager, name)
                    proto_servers.append(self._server_to_proto(name, server_config, is_active, error))

                return assistant_pb2.GetMCPServersResponse(servers=proto_servers)

        except Exception as e:
            logger.error(f"Error getting servers: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.GetMCPServersResponse()

    @get_metadata_interceptor
    async def UpdateMCPServers(self, request, context):
        """Update one or more servers in MCPConfig"""
        try:
            workspace_id = UUID(context.workspace_id)
            user_id = UUID(context.user_id)

            # Convert Struct to dict - expect {"mcpServers": {"name": {...}}}
            request_data = MessageToDict(request.mcp_config, preserving_proto_field_name=True)

            # Extract mcpServers
            mcp_servers = request_data.get('mcpServers', {})
            if not mcp_servers:
                context.set_code(StatusCode.INVALID_ARGUMENT)
                msg = "Request must contain 'mcpServers' field with at least one server"
                context.set_details(msg)
                return assistant_pb2.UpdateMCPServersResponse(success=False)

            updated_servers = []
            errors = []

            with self.db.get_session() as session:
                config = self._get_or_create_config(session, workspace_id, user_id)

                for server_name, server_config in mcp_servers.items():
                    try:
                        # Validate transport config
                        if 'url' not in server_config and 'command' not in server_config:
                            errors.append(f"{server_name}: must have 'url' or 'command'")
                            continue

                        # Update server (add_server overwrites if exists)
                        config.add_server(server_name, server_config)
                        # Store name for later status check
                        updated_servers.append(server_name)

                    except Exception as e:
                        errors.append(f"{server_name}: {str(e)}")

                if updated_servers:
                    session.commit()
                    # Refresh config to get latest state after commit
                    session.refresh(config)

                    # Reinitialize manager
                    manager = self._get_manager(workspace_id, user_id)
                    try:
                        self._run_async(manager.initialize())
                    except Exception as e:
                        logger.warning(f"Manager reinit failed: {e}")

                    # Build proto servers with actual connection status
                    proto_servers = []
                    for server_name in updated_servers:
                        server_config = config.servers.get(server_name)
                        if server_config:
                            is_active, error = self._get_server_status(manager, server_name)
                            proto_servers.append(self._server_to_proto(server_name, server_config, is_active, error))
                else:
                    proto_servers = []

                return assistant_pb2.UpdateMCPServersResponse(
                    servers=proto_servers,
                    success=len(updated_servers) > 0
                )

        except Exception as e:
            return await self._handle_service_error(context, e, "Error updating servers", assistant_pb2.UpdateMCPServersResponse)

    @get_metadata_interceptor
    async def DeleteMCPServers(self, request, context):
        """Delete one or more servers from MCPConfig"""
        try:
            workspace_id = UUID(context.workspace_id)
            user_id = UUID(context.user_id)
            server_names = request.server_names

            if not server_names:
                context.set_code(StatusCode.INVALID_ARGUMENT)
                msg = "Must provide at least one server name to delete"
                context.set_details(msg)
                return assistant_pb2.DeleteMCPServersResponse(success=False)

            deleted_count = 0
            errors = []

            with self.db.get_session() as session:
                config = self._get_or_create_config(session, workspace_id, user_id)

                for server_name in server_names:
                    try:
                        # Check if server exists
                        if server_name not in config.servers:
                            errors.append(f"{server_name}: not found")
                            continue

                        # Remove server
                        config.remove_server(server_name)
                        deleted_count += 1

                    except Exception as e:
                        errors.append(f"{server_name}: {str(e)}")

                if deleted_count > 0:
                    session.commit()

                    # Reinitialize manager
                    manager = self._get_manager(workspace_id, user_id)
                    try:
                        self._run_async(manager.initialize())
                    except Exception as e:
                        logger.warning(f"Manager reinit failed: {e}")

                return assistant_pb2.DeleteMCPServersResponse(
                    success=deleted_count > 0
                )

        except Exception as e:
            return await self._handle_service_error(context, e, "Error deleting servers", assistant_pb2.DeleteMCPServersResponse)
