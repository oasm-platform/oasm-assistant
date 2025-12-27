from typing import List, Optional
from uuid import UUID
from data.database import postgres_db 
from common.logger import logger
from data.database.models import LLMConfig
from common.config.constants import OASM_MODELS
from common.config import configs

class LLMConfigService:
    def __init__(self):
        self.db = postgres_db

    async def sync_oasm_system_models(self, session, workspace_id: UUID, user_id: UUID):
        """Ensure all OASM system models from constants exist in DB for this user/workspace"""
        # Check if ANY config exists for this user/workspace before we add new ones
        any_exists = session.query(LLMConfig).filter(
            LLMConfig.workspace_id == workspace_id,
            LLMConfig.user_id == user_id
        ).first() is not None

        for model_info in OASM_MODELS:
            exists = session.query(LLMConfig).filter(
                LLMConfig.workspace_id == workspace_id,
                LLMConfig.user_id == user_id,
                LLMConfig.provider == model_info["provider"],
                LLMConfig.model == model_info["name"]
            ).first()
            
            if not exists:
                # Only set as preferred if we have a valid OASM key and no other configs exist
                oasm_key_valid = configs.oasm_cloud_apikey and configs.oasm_cloud_apikey != "change_me"
                is_preferred = False
                if not any_exists and model_info.get("is_recommended", False) and oasm_key_valid:
                    is_preferred = True

                new_cfg = LLMConfig(
                    workspace_id=workspace_id,
                    user_id=user_id,
                    provider=model_info["provider"],
                    model=model_info["name"],
                    api_key=model_info["api_key"],
                    is_preferred=is_preferred
                )
                session.add(new_cfg)
        session.commit()

    async def get_llm_configs(
        self, 
        workspace_id: UUID, 
        user_id: UUID,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "asc"
    ) -> tuple[List[LLMConfig], int]:
        try:
            with self.db.get_session() as session:
                # Synchronize OASM models first
                await self.sync_oasm_system_models(session, workspace_id, user_id)

                query = session.query(LLMConfig).filter(
                    LLMConfig.workspace_id == workspace_id,
                    LLMConfig.user_id == user_id
                )

                if search:
                    search_filter = f"%{search}%"
                    query = query.filter(LLMConfig.provider.ilike(search_filter))

                total_count = query.count()

                # Sorting: Always put Preferred at the top
                sort_col = getattr(LLMConfig, sort_by, LLMConfig.created_at)
                if sort_order.lower() == "desc":
                    query = query.order_by(LLMConfig.is_preferred.desc(), sort_col.desc())
                else:
                    query = query.order_by(LLMConfig.is_preferred.desc(), sort_col.asc())

                # Pagination
                if limit > 0:
                    offset = (page - 1) * limit
                    query = query.offset(offset).limit(limit)

                configs = query.all()
                session.expunge_all()

                return configs, total_count
        except Exception as e:
            logger.error("Error getting LLM configs: {}", e)
            raise

    async def update_llm_config(
        self, 
        workspace_id: UUID, 
        user_id: UUID, 
        provider: str, 
        api_key: str, 
        model: Optional[str] = None,
        config_id: Optional[str] = None
    ) -> LLMConfig:
        try:
            with self.db.get_session() as session:
                config = None
                if config_id:
                    # Update existing by ID
                    config = session.query(LLMConfig).filter(
                        LLMConfig.id == UUID(config_id),
                        LLMConfig.workspace_id == workspace_id,
                        LLMConfig.user_id == user_id
                    ).first()
                
                if config and config.api_key == "built-in":
                    raise ValueError("System OASM models cannot be modified")
                
                if not config:
                     # Create NEW
                    config = LLMConfig(
                        workspace_id=workspace_id,
                        user_id=user_id,
                        provider=provider,
                        api_key=api_key,
                        model=model
                    )
                    session.add(config)
                else:
                    # Update existing
                    config.provider = provider 
                    
                    if api_key and not api_key.startswith("****"):
                        config.api_key = api_key
                    if model is not None:
                        config.model = model

                session.flush()
                session.commit()
                session.refresh(config)
                session.expunge(config)
                return config
        except Exception as e:
            logger.error("Error updating LLM config: {}", e)
            raise

    async def delete_llm_config(self, workspace_id: UUID, user_id: UUID, config_id: str) -> bool:
        try:
            with self.db.get_session() as session:
                config = session.query(LLMConfig).filter(
                    LLMConfig.id == UUID(config_id),
                    LLMConfig.workspace_id == workspace_id,
                    LLMConfig.user_id == user_id
                ).first()

                if not config:
                    return False
                
                if config.api_key == "built-in":
                     raise ValueError("System OASM models cannot be deleted")

                session.delete(config)
                session.commit()
                return True
        except Exception as e:
            logger.error("Error deleting LLM config: {}", e)
            raise

    async def set_preferred(self, workspace_id: UUID, user_id: UUID, config_id: str) -> LLMConfig:
        """
        Set a specific LLM config as preferred.
        Automatically unsets all other configs for this user/workspace.
        """
        try:
            with self.db.get_session() as session:
                # First, unset all preferred flags for this user/workspace
                session.query(LLMConfig).filter(
                    LLMConfig.workspace_id == workspace_id,
                    LLMConfig.user_id == user_id
                ).update({"is_preferred": False})
                session.commit()
                
                # Then set the specified config as preferred
                config = session.query(LLMConfig).filter(
                    LLMConfig.id == UUID(config_id),
                    LLMConfig.workspace_id == workspace_id,
                    LLMConfig.user_id == user_id
                ).first()
                
                if not config:
                    raise ValueError(f"LLM config with id {config_id} not found")
                
                config.is_preferred = True
                session.flush()
                session.commit()
                session.refresh(config)
                session.expunge(config)
                return config
        except Exception as e:
            logger.error("Error setting preferred LLM config: {}", e)
            raise

    async def get_available_models(self, workspace_id: UUID, user_id: UUID) -> List[dict]:
        """
        Returns a list of models. 
        Always includes internal OASM models from constants.
        Includes all specifically configured models from the user's LLM configs.
        """
        models = []
        for m in OASM_MODELS:
             models.append({
                "id": m["id"],
                "name": m["name"],
                "provider": m["provider"],
                "description": m["description"],
                "is_active": m["is_active"],
                "is_recommended": m["is_recommended"]
            })
        
        try:
            with self.db.get_session() as session:
                configs = session.query(LLMConfig).filter(
                    LLMConfig.workspace_id == workspace_id,
                    LLMConfig.user_id == user_id
                ).all()
                
                added_ids = {m["id"] for m in models}
                
                for cfg in configs:
                    if not cfg.model or cfg.provider == "oasm":
                        continue
                    
                    # Avoid duplicates
                    model_id = f"{cfg.provider}-{cfg.model}".lower().replace(" ", "-")
                    if model_id in added_ids:
                        continue
                        
                    models.append({
                        "id": model_id,
                        "name": f"{cfg.provider.capitalize()} {cfg.model}",
                        "provider": cfg.provider,
                        "description": f"Configured {cfg.provider} model.",
                        "is_active": True,
                        "is_recommended": cfg.is_preferred
                    })
                    added_ids.add(model_id)
                    
            return models
        except Exception as e:
            logger.error("Error fetching available models: {}", e)
            # Fallback to just the internal model
            return models
