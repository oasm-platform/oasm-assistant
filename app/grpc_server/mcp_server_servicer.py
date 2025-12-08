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
        """Extract and validate mcpServers from protobuf Struct"""
        config_json = MessageToDict(request_config, preserving_proto_field_name=True)
        config_unwrapped = self._unwrap_struct_value(config_json)
        return config_unwrapped.get("mcpServers") or config_unwrapped.get("mcp_servers") or {}

    @get_metadata_interceptor
    async def GetMCPServers(self, request, context):
        try:
            workspace_id = UUID(context.workspace_id)
            user_id = UUID(context.user_id)

            result = self.service.get_server_config(workspace_id, user_id)
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
            if not mcp_servers:
                context.set_code(StatusCode.INVALID_ARGUMENT)
                context.set_details("Request must contain 'mcpServers' field")
                return assistant_pb2.AddMCPServersResponse(success=False)

            success, error, config = self.service.add_servers(workspace_id, user_id, mcp_servers)

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
            if not mcp_servers:
                context.set_code(StatusCode.INVALID_ARGUMENT)
                context.set_details("Request must contain 'mcpServers' field")
                return assistant_pb2.UpdateMCPServersResponse(success=False)

            success, error, config = self.service.update_servers(workspace_id, user_id, mcp_servers)

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
