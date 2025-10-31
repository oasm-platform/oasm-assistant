from app.protos import assistant_pb2, assistant_pb2_grpc
from data.database import postgres_db
from data.database.models import MCPConfig
from tools.mcp_client import MCPManager
from common.logger import logger
from grpc import StatusCode
from app.interceptors import get_metadata_interceptor
from uuid import UUID
from google.protobuf.json_format import MessageToDict, ParseDict
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
        return future.result(timeout=30)

    def _get_manager(self, workspace_id: UUID, user_id: UUID) -> MCPManager:
        """Get or create MCPManager (thread-safe)"""
        key = (str(workspace_id), str(user_id))

        if key not in self._managers:
            with self._manager_lock:
                if key not in self._managers:
                    self._managers[key] = MCPManager(self.db, workspace_id, user_id)

        return self._managers[key]

    def _handle_service_error(self, context, e: Exception, default_message: str, response_class):
        """Common error handling"""
        if isinstance(e, ValueError):
            logger.error(f"Invalid input: {e}")
            context.set_code(StatusCode.INVALID_ARGUMENT)
            context.set_details(str(e))
        else:
            logger.error(f"{default_message}: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
        return response_class(success=False, message=str(e))

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

    def _server_to_proto(self, name: str, server_config: dict) -> assistant_pb2.MCPServer:
        """Convert server config dict to protobuf"""
        proto_server = assistant_pb2.MCPServer(
            id=name,  # Use name as ID
            server_status=server_config.get('status', 'inactive'),
            created_at="",
            updated_at=""
        )

        # Add name to config
        full_config = {"name": name, **server_config}
        ParseDict(full_config, proto_server.mcp_config)

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
    def AddMCPServer(self, request, context):
        """Add a server to MCPConfig JSON"""
        try:
            workspace_id = UUID(context.workspace_id)
            user_id = UUID(context.user_id)

            # Convert Struct to dict
            server_config = MessageToDict(request.mcp_config, preserving_proto_field_name=True)

            # Validate required fields
            server_name = server_config.get('name')
            if not server_name:
                context.set_code(StatusCode.INVALID_ARGUMENT)
                msg = "Server config must contain 'name' field"
                context.set_details(msg)
                return assistant_pb2.AddMCPServerResponse(success=False, message=msg)

            # Validate transport config
            if 'url' not in server_config and 'command' not in server_config:
                context.set_code(StatusCode.INVALID_ARGUMENT)
                msg = "Server must have either 'url' (SSE) or 'command' (STDIO)"
                context.set_details(msg)
                return assistant_pb2.AddMCPServerResponse(success=False, message=msg)

            with self.db.get_session() as session:
                config = self._get_or_create_config(session, workspace_id, user_id)

                # Check if server exists
                if server_name in config.servers:
                    context.set_code(StatusCode.ALREADY_EXISTS)
                    msg = f"Server '{server_name}' already exists"
                    context.set_details(msg)
                    return assistant_pb2.AddMCPServerResponse(success=False, message=msg)

                # Add server to JSON
                config.add_server(server_name, server_config)
                session.commit()
                session.refresh(config)

                # Reinitialize manager with new config
                manager = self._get_manager(workspace_id, user_id)
                try:
                    self._run_async(manager.initialize())
                    message = f"Server '{server_name}' added successfully"
                except Exception as e:
                    message = f"Server '{server_name}' added but connection failed: {e}"

                return assistant_pb2.AddMCPServerResponse(
                    server=self._server_to_proto(server_name, server_config),
                    success=True,
                    message=message
                )

        except Exception as e:
            return self._handle_service_error(context, e, "Error adding server", assistant_pb2.AddMCPServerResponse)

    @get_metadata_interceptor
    def ListMCPServers(self, request, context):
        """List all servers from MCPConfig JSON"""
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
                    # Check if connected
                    is_connected = name in manager._server_configs
                    server_config_copy = server_config.copy()
                    server_config_copy['status'] = 'active' if is_connected else 'inactive'

                    proto_servers.append(self._server_to_proto(name, server_config_copy))

                return assistant_pb2.ListMCPServersResponse(
                    servers=proto_servers,
                    total_count=len(proto_servers)
                )

        except Exception as e:
            logger.error(f"Error listing servers: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.ListMCPServersResponse()

    @get_metadata_interceptor
    def UpdateMCPServer(self, request, context):
        """Update a server in MCPConfig JSON"""
        try:
            workspace_id = UUID(context.workspace_id)
            user_id = UUID(context.user_id)
            server_name = request.mcp_server_id  # Using name as ID

            # Convert Struct to dict
            new_config = MessageToDict(request.mcp_config, preserving_proto_field_name=True)

            with self.db.get_session() as session:
                config = self._get_or_create_config(session, workspace_id, user_id)

                # Check if server exists
                if server_name not in config.servers:
                    context.set_code(StatusCode.NOT_FOUND)
                    msg = f"Server '{server_name}' not found"
                    context.set_details(msg)
                    return assistant_pb2.UpdateMCPServerResponse(success=False, message=msg)

                # Update server
                config.add_server(server_name, new_config)
                session.commit()

                # Reinitialize manager
                manager = self._get_manager(workspace_id, user_id)
                try:
                    self._run_async(manager.initialize())
                    message = f"Server '{server_name}' updated successfully"
                except Exception as e:
                    message = f"Server '{server_name}' updated but reconnection failed: {e}"

                return assistant_pb2.UpdateMCPServerResponse(
                    server=self._server_to_proto(server_name, new_config),
                    success=True,
                    message=message
                )

        except Exception as e:
            return self._handle_service_error(context, e, "Error updating server", assistant_pb2.UpdateMCPServerResponse)

    @get_metadata_interceptor
    def DeleteMCPServer(self, request, context):
        """Delete a server from MCPConfig JSON"""
        try:
            workspace_id = UUID(context.workspace_id)
            user_id = UUID(context.user_id)
            server_name = request.mcp_server_id

            with self.db.get_session() as session:
                config = self._get_or_create_config(session, workspace_id, user_id)

                # Check if server exists
                if server_name not in config.servers:
                    context.set_code(StatusCode.NOT_FOUND)
                    msg = f"Server '{server_name}' not found"
                    context.set_details(msg)
                    return assistant_pb2.DeleteMCPServerResponse(success=False, message=msg)

                # Remove server
                config.remove_server(server_name)
                session.commit()

                # Reinitialize manager
                manager = self._get_manager(workspace_id, user_id)
                try:
                    self._run_async(manager.initialize())
                except Exception as e:
                    logger.error(f"Error reinitializing after delete: {e}")

                return assistant_pb2.DeleteMCPServerResponse(
                    success=True,
                    message=f"Server '{server_name}' deleted successfully"
                )

        except Exception as e:
            return self._handle_service_error(context, e, "Error deleting server", assistant_pb2.DeleteMCPServerResponse)
