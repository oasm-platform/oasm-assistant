from app.protos import assistant_pb2, assistant_pb2_grpc
from app.services.llm_config_service import LLMConfigService
from app.interceptors import get_metadata_interceptor
from common.logger import logger
from grpc import StatusCode
from uuid import UUID

class LLMConfigServiceServicer(assistant_pb2_grpc.LLMConfigServiceServicer):
    def __init__(self, service: LLMConfigService = None):
        self.service = service or LLMConfigService()

    @get_metadata_interceptor
    async def GetLLMConfigs(self, request, context):
        try:
            workspace_id = UUID(context.workspace_id)
            user_id = UUID(context.user_id)

            search = request.search if request.search else None
            page = request.page if request.page > 0 else 1
            limit = request.limit if request.limit > 0 else 20
            sort_by = request.sort_by if request.sort_by else "updated_at"
            sort_order = request.sort_order if request.sort_order else "desc"

            configs, total_count = await self.service.get_llm_configs(
                workspace_id, 
                user_id,
                search=search,
                page=page,
                limit=limit,
                sort_by=sort_by,
                sort_order=sort_order
            )
            
            pb_configs = []
            for cfg in configs:
                # Mask API Key: Show only last 4 chars
                masked_key = cfg.api_key
                if masked_key and len(masked_key) > 4:
                    masked_key = "****" + masked_key[-4:]
                
                pb_cfg = assistant_pb2.LLMConfig(
                    id=str(cfg.id),
                    provider=cfg.provider,
                    api_key=masked_key or "",
                    model=cfg.model or "",
                    is_preferred=cfg.is_preferred,
                    is_editable=str(cfg.id) != "00000000-0000-0000-0000-000000000000",
                )
                pb_configs.append(pb_cfg)
            
            return assistant_pb2.GetLLMConfigsResponse(
                configs=pb_configs,
                total_count=total_count
            )
        except Exception as e:
            logger.error("Error in GetLLMConfigs: {}", e)
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.GetLLMConfigsResponse()

    @get_metadata_interceptor
    async def UpdateLLMConfig(self, request, context):
        try:
            workspace_id = UUID(context.workspace_id)
            user_id = UUID(context.user_id)

            config = await self.service.update_llm_config(
                workspace_id=workspace_id,
                user_id=user_id,
                provider=request.provider,
                api_key=request.api_key,
                model=request.model,
                config_id=request.id if request.id else None
            )

            # Mask API Key for response
            masked_key = config.api_key
            if masked_key and len(masked_key) > 4:
                masked_key = "****" + masked_key[-4:]

            return assistant_pb2.UpdateLLMConfigResponse(
                config=assistant_pb2.LLMConfig(
                    id=str(config.id),
                    provider=config.provider,
                    api_key=masked_key or "",
                    model=config.model or "",
                    is_preferred=config.is_preferred,
                    is_editable=str(config.id) != "00000000-0000-0000-0000-000000000000",
                ),
                success=True
            )
        except Exception as e:
            logger.error("Error in UpdateLLMConfig: {}", e)
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.UpdateLLMConfigResponse(success=False)

    @get_metadata_interceptor
    async def DeleteLLMConfig(self, request, context):
        try:
            workspace_id = UUID(context.workspace_id)
            user_id = UUID(context.user_id)

            success = await self.service.delete_llm_config(
                workspace_id=workspace_id,
                user_id=user_id,
                config_id=request.id
            )
            return assistant_pb2.DeleteLLMConfigResponse(success=success)
        except Exception as e:
            logger.error("Error in DeleteLLMConfig: {}", e)
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.DeleteLLMConfigResponse(success=False)

    @get_metadata_interceptor
    async def SetPreferredLLMConfig(self, request, context):
        try:
            workspace_id = UUID(context.workspace_id)
            user_id = UUID(context.user_id)

            config = await self.service.set_preferred(
                workspace_id=workspace_id,
                user_id=user_id,
                config_id=request.id
            )

            # Mask API Key for response
            masked_key = config.api_key
            if masked_key and len(masked_key) > 4:
                masked_key = "****" + masked_key[-4:]

            return assistant_pb2.SetPreferredLLMConfigResponse(
                config=assistant_pb2.LLMConfig(
                    id=str(config.id),
                    provider=config.provider,
                    api_key=masked_key or "",
                    model=config.model or "",
                    is_preferred=config.is_preferred,
                    is_editable=str(config.id) != "00000000-0000-0000-0000-000000000000",
                ),
                success=True
            )
        except Exception as e:
            logger.error("Error in SetPreferredLLMConfig: {}", e)
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.SetPreferredLLMConfigResponse(success=False)

    @get_metadata_interceptor
    async def GetAvailableModels(self, request, context):
        try:
            workspace_id = UUID(context.workspace_id)
            user_id = UUID(context.user_id)

            models = await self.service.get_available_models(workspace_id, user_id)
            
            pb_models = []
            for m in models:
                pb_models.append(assistant_pb2.ModelInfo(
                    id=m["id"],
                    name=m["name"],
                    provider=m["provider"],
                    description=m["description"],
                    is_active=m["is_active"],
                    is_recommended=m.get("is_recommended", False)
                ))
            
            return assistant_pb2.GetAvailableModelsResponse(models=pb_models)
        except Exception as e:
            logger.error("Error in GetAvailableModels: {}", e)
            context.set_code(StatusCode.INTERNAL)
            context.set_details(str(e))
            return assistant_pb2.GetAvailableModelsResponse()
