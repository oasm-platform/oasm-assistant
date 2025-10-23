from app.protos import assistant_pb2, assistant_pb2_grpc
from data.database import postgres_db
from data.database.models import MCPServer
from data.database.models.mcp_servers import ServerStatus
from tools.mcp_client import MCPManager
from common.logger import logger
from grpc import StatusCode
from app.interceptors import get_metadata_interceptor
from uuid import UUID
from google.protobuf.json_format import MessageToDict, ParseDict
import asyncio
import threading
from typing import Optional
from concurrent.futures import ThreadPoolExecutor


class MCPServerService(assistant_pb2_grpc.MCPServerServiceServicer):
    """MCP Server Service implementation - simplified with JSON config"""

    def __init__(self):
        self.db = postgres_db
        self._managers = {}  # Cache managers by (workspace_id, user_id)
        self._manager_lock = threading.Lock()  # Thread-safe access to managers
        self._async_loop = None
        self._async_thread = None
        self._executor = ThreadPoolExecutor(max_workers=5)
        self._setup_async_loop()

    def _setup_async_loop(self):
        """Setup a dedicated event loop in a separate thread for async operations"""
        def run_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()

        self._async_loop = asyncio.new_event_loop()
        self._async_thread = threading.Thread(target=run_loop, args=(self._async_loop,), daemon=True)
        self._async_thread.start()

    def _run_async(self, coro):
        """Run async coroutine in the dedicated event loop and wait for result"""
        future = asyncio.run_coroutine_threadsafe(coro, self._async_loop)
        return future.result(timeout=30)  # 30 second timeout

    def _get_manager(self, workspace_id: UUID, user_id: UUID) -> MCPManager:
        """Get or create MCPManager for a specific workspace and user (thread-safe)"""
        key = (str(workspace_id), str(user_id))

        # Double-checked locking pattern for performance
        if key not in self._managers:
            with self._manager_lock:
                # Check again inside lock to avoid race condition
                if key not in self._managers:
                    self._managers[key] = MCPManager(self.db, workspace_id, user_id)

        return self._managers[key]

    def _handle_service_error(self, context, e: Exception, default_message: str, response_class):
        """Common error handling for all service methods"""
        if isinstance(e, ValueError):
            logger.error(f"Invalid input: {e}")
            context.set_code(StatusCode.INVALID_ARGUMENT)
            context.set_details(str(e))
        else:
            logger.error(f"{default_message}: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
        return response_class(success=False, message=str(e))

    def _get_server_by_id(self, session, server_id: UUID, workspace_id: UUID, user_id: UUID) -> Optional[MCPServer]:
        """Get server by ID with workspace and user validation"""
        return session.query(MCPServer).filter(
            MCPServer.id == server_id,
            MCPServer.workspace_id == workspace_id,
            MCPServer.user_id == user_id
        ).first()

    def _check_server_exists(self, session, name: str, workspace_id: UUID, user_id: UUID) -> bool:
        """Check if server with name already exists for workspace and user"""
        servers = session.query(MCPServer).filter(
            MCPServer.workspace_id == workspace_id,
            MCPServer.user_id == user_id
        ).all()

        for server in servers:
            if server.name == name:
                return True
        return False

    def _handle_async_connection(self, manager: MCPManager, server: MCPServer, operation: str) -> Optional[str]:
        """Handle async connection/reconnection, return error message if failed"""
        try:
            if operation == "initialize":
                if not manager.clients:
                    self._run_async(manager.initialize())
                else:
                    self._run_async(manager._connect(server))
            elif operation == "reconnect":
                if server.name in manager.clients:
                    self._run_async(manager.clients[server.name].disconnect())
                    del manager.clients[server.name]
                if server.is_active:
                    self._run_async(manager._connect(server))
            elif operation == "disconnect":
                if server.name in manager.clients:
                    self._run_async(manager.clients[server.name].disconnect())
                    del manager.clients[server.name]
            return None
        except Exception as e:
            logger.error(f"Failed to {operation} server {server.name}: {e}")
            return str(e)

    def cleanup(self):
        """Cleanup resources when service is shutting down"""
        try:
            # Shutdown all managers
            for manager in self._managers.values():
                try:
                    self._run_async(manager.shutdown())
                except Exception as e:
                    logger.error(f"Error shutting down manager: {e}")

            # Stop the async loop
            if self._async_loop and self._async_loop.is_running():
                self._async_loop.call_soon_threadsafe(self._async_loop.stop)

            # Shutdown executor
            if self._executor:
                self._executor.shutdown(wait=True)

            logger.info("MCPServerService cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def _server_to_proto(self, server: MCPServer) -> assistant_pb2.MCPServer:
        """Convert SQLAlchemy MCPServer model to protobuf message"""
        if not server:
            return None

        server_dict = server.to_dict()

        # Convert mcp_config dict to Struct
        proto_server = assistant_pb2.MCPServer(
            id=str(server_dict.get('id', '')),
            server_status=server_dict.get('server_status', 'inactive'),
            created_at=server_dict.get('created_at', ''),
            updated_at=server_dict.get('updated_at', '')
        )

        # Use ParseDict to convert dict to Struct
        mcp_config = server_dict.get('mcp_config', {})
        if mcp_config:
            ParseDict(mcp_config, proto_server.mcp_config)

        return proto_server

    @get_metadata_interceptor
    def AddMCPServer(self, request, context):
        """Add a new MCP server"""
        try:
            workspace_id = UUID(context.workspace_id)
            user_id = UUID(context.user_id)

            # Convert Struct to dict
            mcp_config = MessageToDict(request.mcp_config, preserving_proto_field_name=True)

            # Validate required fields in config
            if not mcp_config.get('name'):
                context.set_code(StatusCode.INVALID_ARGUMENT)
                msg = "mcp_config must contain 'name' field"
                context.set_details(msg)
                return assistant_pb2.AddMCPServerResponse(success=False, message=msg)

            with self.db.get_session() as session:
                # Check if server already exists
                if self._check_server_exists(session, mcp_config['name'], workspace_id, user_id):
                    context.set_code(StatusCode.ALREADY_EXISTS)
                    msg = f"Server '{mcp_config['name']}' already exists"
                    context.set_details(msg)
                    return assistant_pb2.AddMCPServerResponse(success=False, message=msg)

                # Create server
                server = MCPServer(
                    workspace_id=workspace_id,
                    user_id=user_id,
                    mcp_config=mcp_config
                )

                # Validate config before saving
                is_valid, error_msg = server.validate_config()
                if not is_valid:
                    context.set_code(StatusCode.INVALID_ARGUMENT)
                    context.set_details(error_msg)
                    return assistant_pb2.AddMCPServerResponse(success=False, message=error_msg)

                session.add(server)
                session.commit()
                session.refresh(server)

                # Connect if active
                manager = self._get_manager(workspace_id, user_id)
                connection_error = self._handle_async_connection(manager, server, "initialize") if server.mcp_config.get('is_active', False) else None

                message = f"Server '{server.name}' added successfully"
                if connection_error:
                    message += f", but connection failed: {connection_error}"

                return assistant_pb2.AddMCPServerResponse(
                    server=self._server_to_proto(server),
                    success=True,
                    message=message
                )

        except Exception as e:
            return self._handle_service_error(context, e, "Error adding MCP server", assistant_pb2.AddMCPServerResponse)

    @get_metadata_interceptor
    def ListMCPServers(self, request, context):
        """List all MCP servers for a workspace and user, checking and updating their active status"""
        try:
            workspace_id = UUID(context.workspace_id)
            user_id = UUID(context.user_id)

            with self.db.get_session() as session:
                query = session.query(MCPServer).filter(
                    MCPServer.workspace_id == workspace_id,
                    MCPServer.user_id == user_id
                )

                servers = query.all()

                # Get manager to check connection status
                manager = self._get_manager(workspace_id, user_id)
                
                # Ensure manager has initialized connections
                # Only initialize if clients haven't been loaded yet
                if not manager.clients:
                    try:
                        self._run_async(manager.initialize())
                    except Exception as e:
                        logger.error(f"Failed to initialize MCP manager: {e}")

                # Update server_status for each server based on actual connection
                for server in servers:
                    # If manually disabled by user, don't check connection
                    if server.server_status == ServerStatus.DISABLED.value:
                        # Keep as disabled, don't check connection
                        continue

                    # Check actual connection status
                    client = manager.clients.get(server.name)
                    if client:
                        # Use the async is_connected method through the event loop
                        try:
                            is_connected = self._run_async(client.is_connected())
                        except Exception:
                            # If async check fails, assume disconnected
                            is_connected = False
                    else:
                        # If no client exists, try to connect to this specific server
                        try:
                            self._run_async(manager._connect(server))
                            # Check if connection was successful
                            client = manager.clients.get(server.name)
                            if client:
                                is_connected = self._run_async(client.is_connected())
                            else:
                                is_connected = False
                        except Exception as e:
                            is_connected = False

                    # Determine new status based on connection
                    new_status = ServerStatus.ACTIVE.value if is_connected else ServerStatus.INACTIVE.value

                    if server.server_status != new_status:
                        old_status = server.server_status
                        server.server_status = new_status

                    # Also update is_active in config for backward compatibility
                    old_is_active = server.mcp_config.get('is_active', False)
                    new_is_active = is_connected

                    if old_is_active != new_is_active:
                        updated_config = server.mcp_config.copy()
                        updated_config['is_active'] = new_is_active
                        server.mcp_config = updated_config

                # Commit all updates
                session.commit()

                # Sort by priority
                servers.sort(key=lambda s: s.mcp_config.get('priority', 0), reverse=True)

                return assistant_pb2.ListMCPServersResponse(
                    servers=[self._server_to_proto(s) for s in servers],
                    total_count=len(servers)
                )

        except Exception as e:
            logger.error(f"Error listing MCP servers: {e}")
            context.set_code(StatusCode.INTERNAL if not isinstance(e, ValueError) else StatusCode.INVALID_ARGUMENT)
            context.set_details(str(e))
            return assistant_pb2.ListMCPServersResponse()

    @get_metadata_interceptor
    def UpdateMCPServer(self, request, context):
        """Update an existing MCP server"""
        try:
            workspace_id = UUID(context.workspace_id)
            user_id = UUID(context.user_id)
            server_id = UUID(request.mcp_server_id)

            # Convert Struct to dict
            new_config = MessageToDict(request.mcp_config, preserving_proto_field_name=True)

            with self.db.get_session() as session:
                server = self._get_server_by_id(session, server_id, workspace_id, user_id)
                if not server:
                    context.set_code(StatusCode.NOT_FOUND)
                    msg = "Server not found"
                    context.set_details(msg)
                    return assistant_pb2.UpdateMCPServerResponse(success=False, message=msg)

                # Update server_status if provided
                if request.server_status:
                    # Validate status value
                    valid_statuses = [ServerStatus.ACTIVE.value, ServerStatus.INACTIVE.value, ServerStatus.DISABLED.value]
                    if request.server_status not in valid_statuses:
                        context.set_code(StatusCode.INVALID_ARGUMENT)
                        msg = f"Invalid server_status: {request.server_status}. Must be one of: {', '.join(valid_statuses)}"
                        context.set_details(msg)
                        return assistant_pb2.UpdateMCPServerResponse(success=False, message=msg)

                    if request.server_status != server.server_status:
                        server.server_status = request.server_status

                # Check if critical fields changed (requires reconnection)
                old_config = server.mcp_config
                needs_reconnect = (
                    new_config.get('command') != old_config.get('command') or
                    new_config.get('args') != old_config.get('args') or
                    new_config.get('url') != old_config.get('url') or
                    new_config.get('is_active') != old_config.get('is_active')
                )

                # Update config
                server.mcp_config = new_config
                session.commit()
                session.refresh(server)

                manager = self._get_manager(workspace_id, user_id)
                reconnection_error = self._handle_async_connection(manager, server, "reconnect") if needs_reconnect else None

                message = f"Server '{server.name}' updated successfully"
                if reconnection_error:
                    message += f", but reconnection failed: {reconnection_error}"

                return assistant_pb2.UpdateMCPServerResponse(
                    server=self._server_to_proto(server),
                    success=True,
                    message=message
                )

        except Exception as e:
            return self._handle_service_error(context, e, "Error updating MCP server", assistant_pb2.UpdateMCPServerResponse)

    @get_metadata_interceptor
    def DeleteMCPServer(self, request, context):
        """Delete an MCP server"""
        try:
            workspace_id = UUID(context.workspace_id)
            user_id = UUID(context.user_id)
            server_id = UUID(request.mcp_server_id)

            with self.db.get_session() as session:
                server = self._get_server_by_id(session, server_id, workspace_id, user_id)
                if not server:
                    context.set_code(StatusCode.NOT_FOUND)
                    msg = "Server not found"
                    context.set_details(msg)
                    return assistant_pb2.DeleteMCPServerResponse(success=False, message=msg)

                server_name = server.name

                # Disconnect before deletion
                manager = self._get_manager(workspace_id, user_id)
                disconnection_error = self._handle_async_connection(manager, server, "disconnect")

                # Delete from database
                session.delete(server)
                session.commit()

                message = f"Server '{server_name}' deleted successfully"
                if disconnection_error:
                    message += f", but disconnection failed: {disconnection_error}"

                return assistant_pb2.DeleteMCPServerResponse(success=True, message=message)

        except Exception as e:
            return self._handle_service_error(context, e, "Error deleting MCP server", assistant_pb2.DeleteMCPServerResponse)
