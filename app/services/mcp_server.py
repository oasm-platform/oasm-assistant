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
import json
from typing import Dict, Tuple, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor


class MCPServerService(assistant_pb2_grpc.MCPServerServiceServicer):
    """MCP Server Service - manages MCPConfig (JSON with multiple servers)"""

    def __init__(self):
        self.db = postgres_db
        self._managers: Dict[Tuple[str, str], MCPManager] = {}
        self._manager_lock = threading.Lock()
        self._async_loop: Optional[asyncio.AbstractEventLoop] = None
        self._async_thread: Optional[threading.Thread] = None
        self._executor = ThreadPoolExecutor(max_workers=5)
        self.mcp_timeout = configs.mcp_timeout
        self._setup_async_loop()

    def _unwrap_struct_value(self, data: Any) -> Any:
        """Recursively unwrap Protobuf Struct values to native Python types."""
        if not isinstance(data, dict):
            return data

        # Unwrap typed values
        type_mappings = {
            'stringValue': lambda d: d['stringValue'],
            'boolValue': lambda d: d['boolValue'],
            'numberValue': lambda d: d['numberValue'],
            'nullValue': lambda d: None
        }
        
        for key, extractor in type_mappings.items():
            if key in data:
                return extractor(data)

        # Unwrap struct
        if 'structValue' in data and 'fields' in data['structValue']:
            return {k: self._unwrap_struct_value(v) for k, v in data['structValue']['fields'].items()}
        
        if 'fields' in data and len(data) == 1:
            return {k: self._unwrap_struct_value(v) for k, v in data['fields'].items()}

        # Unwrap list
        if 'listValue' in data and 'values' in data['listValue']:
            return [self._unwrap_struct_value(v) for v in data['listValue']['values']]

        # Recursively process nested dicts
        return {k: self._unwrap_struct_value(v) for k, v in data.items()}

    def _setup_async_loop(self) -> None:
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

    def _get_server_status(self, manager: MCPManager, server_name: str, test_connection: bool = True) -> Tuple[bool, Optional[str]]:
        """Get actual server status by checking manager state"""
        return manager.get_server_status(server_name, test_connection=test_connection)

    def _server_to_proto(self, name: str, server_config: dict, is_active: bool, error: Optional[str] = None) -> assistant_pb2.MCPServer:
        """Convert server config dict to protobuf"""
        config_struct = Struct()
        config_struct.update({name: server_config})

        return assistant_pb2.MCPServer(
            config=config_struct,
            active=True if is_active else None,
            error=error or "Unknown error" if not is_active else None
        )

    def _extract_mcp_servers(self, request_config: Struct) -> Dict[str, Any]:
        """Extract and validate mcpServers from protobuf Struct"""
        config_json = MessageToDict(request_config, preserving_proto_field_name=True)
        config_unwrapped = self._unwrap_struct_value(config_json)
        return config_unwrapped.get("mcpServers") or config_unwrapped.get("mcp_servers") or {}

    def _validate_server_config(self, server_config: dict) -> bool:
        """Validate that server has required transport config"""
        return "url" in server_config or "command" in server_config

    def _initialize_manager(self, manager: MCPManager) -> None:
        """Initialize manager if not already initialized"""
        if not manager._initialized:
            try:
                self._run_async(manager.initialize())
            except Exception as e:
                logger.warning(f"Manager initialization failed: {e}")

    def _process_servers_batch(
        self, 
        config: MCPConfig, 
        mcp_servers: Dict[str, Any], 
        operation: str  # "add" or "update"
    ) -> Tuple[List[str], List[str]]:
        """
        Process a batch of servers for add/update operations
        
        Returns:
            Tuple of (successful_servers, errors)
        """
        successful = []
        errors = []

        for server_name, server_config in mcp_servers.items():
            try:
                if not self._validate_server_config(server_config):
                    errors.append(f"{server_name}: must have 'url' or 'command'")
                    continue

                if operation == "add" and server_name in config.servers:
                    errors.append(f"{server_name}: already exists")
                    continue

                config.add_server(server_name, server_config)
                successful.append(server_name)

            except Exception as e:
                errors.append(f"{server_name}: {str(e)}")

        return successful, errors

    def _build_proto_servers(
        self, 
        config: MCPConfig, 
        manager: MCPManager, 
        server_names: List[str]
    ) -> List[assistant_pb2.MCPServer]:
        """Build protobuf server list with status"""
        proto_servers = []
        
        for server_name in server_names:
            server_config = config.servers.get(server_name)
            if not server_config:
                continue
                
            try:
                is_active, error = self._get_server_status(manager, server_name)
                proto_servers.append(self._server_to_proto(server_name, server_config, is_active, error))
            except Exception as e:
                logger.warning(f"Failed to get status for {server_name}: {e}")
                continue

        return proto_servers

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

    def _enrich_config_with_status(self, config: MCPConfig, manager: MCPManager) -> Dict[str, Any]:
        """
        Enrich MCP config with live status for each server.
        
        Returns dict with active/status/error fields for each server.
        """
        enriched_servers = {}

        for name, server_config in config.servers.items():
            is_active, error = self._get_server_status(manager, name)
            
            enriched_server = dict(server_config)
            enriched_server["active"] = is_active
            
            # Determine status: active > disabled > error
            if is_active:
                enriched_server["status"] = "active"
            elif server_config.get("disabled"):
                enriched_server["status"] = "disabled"
            else:
                enriched_server["status"] = "error"
            
            if error:
                enriched_server["error"] = error
            
            enriched_servers[name] = enriched_server
            logger.debug(f"Server '{name}': active={is_active}, status={enriched_server['status']}")

        return {"mcpServers": enriched_servers}

    def _build_enriched_response(self, config: MCPConfig, manager: MCPManager) -> str:
        """
        Build enriched response JSON with metadata and server status.
        Used by Get/Add/Update operations for consistent response format.
        """
        # Enrich config with status
        enriched_config = self._enrich_config_with_status(config, manager)
        
        # Build response with metadata
        config_metadata = config.to_dict()
        response_data = {
            "id": config_metadata["id"],
            "workspace_id": config_metadata["workspace_id"],
            "user_id": config_metadata["user_id"],
            "created_at": config_metadata["created_at"],
            "updated_at": config_metadata["updated_at"],
            "mcpServers": enriched_config["mcpServers"]
        }
        
        logger.info(f"Returning enriched config with {len(enriched_config['mcpServers'])} servers")
        return json.dumps(response_data)

    @get_metadata_interceptor
    async def GetMCPServers(self, request, context):
        """Get all servers from MCPConfig with enriched status and metadata"""
        try:
            workspace_id = UUID(context.workspace_id)
            user_id = UUID(context.user_id)

            with self.db.get_session() as session:
                config = self._get_or_create_config(session, workspace_id, user_id)
                manager = self._get_manager(workspace_id, user_id)
                
                # Initialize manager if needed
                self._initialize_manager(manager)

                # Build enriched response
                mcp_config_json = self._build_enriched_response(config, manager)

                return assistant_pb2.GetMCPServersResponse(
                    servers=[],  # Keep for backward compatibility
                    mcp_config_json=mcp_config_json
                )

        except Exception as e:
            logger.error(f"Error getting servers: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.GetMCPServersResponse()


    @get_metadata_interceptor
    async def AddMCPServers(self, request, context):
        """Add one or more MCP servers to the MCPConfig."""
        try:
            workspace_id = UUID(context.workspace_id)
            user_id = UUID(context.user_id)

            # Extract and validate mcpServers
            mcp_servers = self._extract_mcp_servers(request.mcp_config)
            if not mcp_servers:
                context.set_code(StatusCode.INVALID_ARGUMENT)
                context.set_details("Request must contain 'mcpServers' field with at least one server")
                return assistant_pb2.AddMCPServersResponse(success=False)

            with self.db.get_session() as session:
                config = self._get_or_create_config(session, workspace_id, user_id)
                
                # Process servers batch
                added_servers, errors = self._process_servers_batch(config, mcp_servers, operation="add")

                if added_servers:
                    session.commit()
                    session.refresh(config)

                    # Reinitialize manager
                    manager = self._get_manager(workspace_id, user_id)
                    self._initialize_manager(manager)

                    # Build enriched response
                    mcp_config_json = self._build_enriched_response(config, manager)
                    
                    return assistant_pb2.AddMCPServersResponse(
                        servers=[],  # Keep for backward compatibility
                        success=True,
                        mcp_config_json=mcp_config_json
                    )
                else:
                    return assistant_pb2.AddMCPServersResponse(
                        servers=[],
                        success=False,
                        error="No servers were added"
                    )

        except Exception as e:
            return await self._handle_service_error(
                context, e, "Error adding servers", assistant_pb2.AddMCPServersResponse
            )

    @get_metadata_interceptor
    async def UpdateMCPServers(self, request, context):
        """Update one or more servers in MCPConfig"""
        try:
            workspace_id = UUID(context.workspace_id)
            user_id = UUID(context.user_id)

            # Extract and validate mcpServers
            mcp_servers = self._extract_mcp_servers(request.mcp_config)
            if not mcp_servers:
                context.set_code(StatusCode.INVALID_ARGUMENT)
                context.set_details("Request must contain 'mcpServers' field with at least one server")
                return assistant_pb2.UpdateMCPServersResponse(success=False)

            with self.db.get_session() as session:
                config = self._get_or_create_config(session, workspace_id, user_id)
                
                # Process servers batch (update allows overwriting)
                updated_servers, errors = self._process_servers_batch(config, mcp_servers, operation="update")

                if updated_servers:
                    session.commit()
                    session.refresh(config)

                    # Reinitialize manager
                    manager = self._get_manager(workspace_id, user_id)
                    self._initialize_manager(manager)

                    # Build enriched response
                    mcp_config_json = self._build_enriched_response(config, manager)
                    
                    return assistant_pb2.UpdateMCPServersResponse(
                        servers=[],  # Keep for backward compatibility
                        success=True,
                        mcp_config_json=mcp_config_json
                    )
                else:
                    return assistant_pb2.UpdateMCPServersResponse(
                        servers=[],
                        success=False
                    )

        except Exception as e:
            return await self._handle_service_error(
                context, e, "Error updating servers", assistant_pb2.UpdateMCPServersResponse
            )


    @get_metadata_interceptor
    async def DeleteMCPServers(self, request, context):
        """Delete MCP config by ID"""
        try:
            workspace_id = UUID(context.workspace_id)
            user_id = UUID(context.user_id)
            config_id = request.id

            if not config_id:
                context.set_code(StatusCode.INVALID_ARGUMENT)
                context.set_details("Must provide config ID to delete")
                return assistant_pb2.DeleteMCPServersResponse(
                    success=False,
                    message="Config ID is required"
                )

            with self.db.get_session() as session:
                # Find config by ID, workspace_id, and user_id
                config = session.query(MCPConfig).filter(
                    MCPConfig.id == UUID(config_id),
                    MCPConfig.workspace_id == workspace_id,
                    MCPConfig.user_id == user_id
                ).first()

                if not config:
                    context.set_code(StatusCode.NOT_FOUND)
                    context.set_details(f"MCP Config with ID {config_id} not found")
                    return assistant_pb2.DeleteMCPServersResponse(
                        success=False,
                        message=f"MCP Config with ID {config_id} not found"
                    )

                # Count servers before deletion
                server_count = len(config.servers)
                
                # Delete the entire config
                session.delete(config)
                session.commit()

                # Reinitialize manager to clear cached connections
                manager = self._get_manager(workspace_id, user_id)
                self._initialize_manager(manager)

                message = f"Successfully deleted MCP config with {server_count} server(s)"
                logger.info(f"Deleted MCP config {config_id} with {server_count} servers")
                
                return assistant_pb2.DeleteMCPServersResponse(
                    success=True,
                    message=message
                )

        except ValueError as e:
            context.set_code(StatusCode.INVALID_ARGUMENT)
            context.set_details(f"Invalid config ID format: {str(e)}")
            return assistant_pb2.DeleteMCPServersResponse(
                success=False,
                message=f"Invalid config ID format: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Error deleting MCP config: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.DeleteMCPServersResponse(
                success=False,
                message=f"Error deleting MCP config: {str(e)}"
            )
