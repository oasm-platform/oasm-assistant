from app.protos import assistant_pb2, assistant_pb2_grpc
from app.services.mcp_server_service import MCPServerService
from app.interceptors import get_metadata_interceptor
from common.logger import logger
from grpc import StatusCode
from uuid import UUID
from google.protobuf.json_format import MessageToDict
import json

class MCPServerServiceServicer(assistant_pb2_grpc.MCPServerServiceServicer):
    def __init__(self, service: MCPServerService = None):
        self.service = service or MCPServerService()

    def _unwrap_struct_value(self, data):
        """Recursively unwrap Protobuf Struct values to native Python types."""
        if not isinstance(data, dict):
            return data
        type_mappings = {
            'stringValue': lambda d: d['stringValue'],
            'boolValue': lambda d: d['boolValue'],
            'numberValue': lambda d: d['numberValue'],
            'nullValue': lambda d: None
        }
        for key, extractor in type_mappings.items():
            if key in data:
                return extractor(data)
        if 'structValue' in data and 'fields' in data['structValue']:
            return {k: self._unwrap_struct_value(v) for k, v in data['structValue']['fields'].items()}
        if 'fields' in data and len(data) == 1:
            return {k: self._unwrap_struct_value(v) for k, v in data['fields'].items()}
        if 'listValue' in data and 'values' in data['listValue']:
            return [self._unwrap_struct_value(v) for v in data['listValue']['values']]
        return {k: self._unwrap_struct_value(v) for k, v in data.items()}

    def _extract_mcp_servers(self, request_config):
        """Extract mcpServers from protobuf Struct. Returns None if field is missing."""
        config_json = MessageToDict(request_config, preserving_proto_field_name=True)
        config_unwrapped = self._unwrap_struct_value(config_json)
        if "mcpServers" in config_unwrapped:
            return config_unwrapped["mcpServers"]
        if "mcp_servers" in config_unwrapped:
            return config_unwrapped["mcp_servers"]
        return None

    @get_metadata_interceptor
    async def GetMCPServers(self, request, context):
        try:
            workspace_id = UUID(context.workspace_id)
            user_id = UUID(context.user_id)

            # Always include tools and resources for UI display
            result = await self.service.get_server_config(
                workspace_id, 
                user_id,
                skip_health_check=False, # Test real connections
                include_tools=True         # Include tools and resources
            )
            mcp_config_json = json.dumps(result)

            return assistant_pb2.GetMCPServersResponse(
                servers=[],
                mcp_config_json=mcp_config_json
            )

        except Exception as e:
            logger.error(f"Error getting servers: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.GetMCPServersResponse()

    @get_metadata_interceptor
    async def AddMCPServers(self, request, context):
        try:
            workspace_id = UUID(context.workspace_id)
            user_id = UUID(context.user_id)

            mcp_servers = self._extract_mcp_servers(request.mcp_config)
            if mcp_servers is None:
                context.set_code(StatusCode.INVALID_ARGUMENT)
                context.set_details("Request must contain 'mcpServers' field")
                return assistant_pb2.AddMCPServersResponse(success=False)

            success, error, config = await self.service.add_servers(workspace_id, user_id, mcp_servers)

            if success:
                return assistant_pb2.AddMCPServersResponse(
                    servers=[], success=True, mcp_config_json=json.dumps(config)
                )
            else:
                 return assistant_pb2.AddMCPServersResponse(
                    servers=[], success=False, error=error or "Unknown error"
                )

        except Exception as e:
            logger.error(f"Error adding servers: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.AddMCPServersResponse(success=False)

    @get_metadata_interceptor
    async def UpdateMCPServers(self, request, context):
        try:
            workspace_id = UUID(context.workspace_id)
            user_id = UUID(context.user_id)

            mcp_servers = self._extract_mcp_servers(request.mcp_config)
            if mcp_servers is None:
                context.set_code(StatusCode.INVALID_ARGUMENT)
                context.set_details("Request must contain 'mcpServers' field")
                return assistant_pb2.UpdateMCPServersResponse(success=False)

            success, error, config = await self.service.update_servers(workspace_id, user_id, mcp_servers)

            if success:
                return assistant_pb2.UpdateMCPServersResponse(
                    servers=[], success=True, mcp_config_json=json.dumps(config)
                )
            else:
                 return assistant_pb2.UpdateMCPServersResponse(
                    servers=[], success=False
                )
        except Exception as e:
            logger.error(f"Error updating servers: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.UpdateMCPServersResponse(success=False)

    @get_metadata_interceptor
    async def DeleteMCPServers(self, request, context):
        try:
            workspace_id = UUID(context.workspace_id)
            user_id = UUID(context.user_id)
            config_id = request.id

            if not config_id:
                context.set_code(StatusCode.INVALID_ARGUMENT)
                context.set_details("Must provide config ID")
                return assistant_pb2.DeleteMCPServersResponse(success=False, message="Config ID required")

            success, message = self.service.delete_config(config_id, workspace_id, user_id)
            
            if not success and "not found" in message:
                context.set_code(StatusCode.NOT_FOUND)
            
            return assistant_pb2.DeleteMCPServersResponse(success=success, message=message)

        except Exception as e:
            logger.error(f"Error deleting config: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.DeleteMCPServersResponse(success=False, message=str(e))

    @get_metadata_interceptor
    async def GetMCPServerHealth(self, request, context):
        try:
            workspace_id = UUID(context.workspace_id)
            user_id = UUID(context.user_id)
            server_name = request.server_name

            if not server_name:
                context.set_code(StatusCode.INVALID_ARGUMENT)
                context.set_details("Must provide server name")
                return assistant_pb2.GetMCPServerHealthResponse(
                    is_active=False, 
                    status="error", 
                    error="Server name required"
                )

            is_active, status, error = await self.service.get_server_health(workspace_id, user_id, server_name)
            
            return assistant_pb2.GetMCPServerHealthResponse(
                is_active=is_active,
                status=status,
                error=error or ""
            )

        except Exception as e:
            logger.error(f"Error checking server health: {e}")
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.GetMCPServerHealthResponse(
                is_active=False,
                status="error",
                error=str(e)
            )
