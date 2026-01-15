from typing import List, Optional
from uuid import UUID
from data.database import postgres_db 
from common.logger import logger
from data.database.models import LLMConfig
from common.config import configs

class LLMConfigService:
    def __init__(self):
        self.db = postgres_db


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

                db_configs = query.all()
                session.expunge_all()

                # Inject default system config if configured
                if configs.llm.provider and configs.llm.model_name:
                    # Check if it matches search
                    matches_search = True
                    if search:
                        search_term = search.lower()
                        if search_term not in configs.llm.provider.lower():
                            matches_search = False

                    if matches_search:
                        total_count += 1
                        
                        if page == 1:
                            # Check if any DB config is preferred
                            any_preferred = any(cfg.is_preferred for cfg in db_configs)
                            
                            default_config = self._create_default_llm_config(
                                workspace_id=workspace_id,
                                user_id=user_id,
                                is_preferred=not any_preferred
                            )
                            # Prepend to list
                            db_configs.insert(0, default_config)

                return db_configs, total_count
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
        config_id: Optional[str] = None,
        api_url: Optional[str] = None
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
                    raise ValueError("Built-in system models cannot be modified")
                
                if not config:
                     # Create NEW
                    config = LLMConfig(
                        workspace_id=workspace_id,
                        user_id=user_id,
                        provider=provider,
                        api_key=api_key,
                        model=model,
                        api_url=api_url
                    )
                    session.add(config)
                else:
                    # Update existing
                    config.provider = provider 
                    
                    if api_key and not api_key.startswith("****"):
                        config.api_key = api_key
                    if model is not None:
                        config.model = model
                    if api_url is not None:
                        config.api_url = api_url

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
                     raise ValueError("Built-in system models cannot be deleted")

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
            # Handle special case for system default config
            if str(config_id) == "00000000-0000-0000-0000-000000000000":
                with self.db.get_session() as session:
                    # Unset all preferred flags
                    session.query(LLMConfig).filter(
                        LLMConfig.workspace_id == workspace_id,
                        LLMConfig.user_id == user_id
                    ).update({"is_preferred": False})
                    session.commit()
                
                # Return the virtual default config with is_preferred=True
                return self._create_default_llm_config(workspace_id, user_id, is_preferred=True)

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
        Returns a list of models from the user's LLM configs.
        Always includes the default model from .env if configured.
        """
        models = []
        
        try:
            with self.db.get_session() as session:
                configs_list = session.query(LLMConfig).filter(
                    LLMConfig.workspace_id == workspace_id,
                    LLMConfig.user_id == user_id
                ).all()
                
                # Check if any user config is preferred
                any_preferred = any(cfg.is_preferred for cfg in configs_list)
                
                # Add default model from .env if configured
                if configs.llm.provider and configs.llm.model_name:
                    default_model_id = f"{configs.llm.provider}-{configs.llm.model_name}".lower().replace(" ", "-").replace("/", "-")
                    models.append({
                        "id": default_model_id,
                        "name": configs.llm.model_name,
                        "provider": configs.llm.provider,
                        "description": configs.llm.description or f"Default {configs.llm.provider} model from configuration",
                        "is_active": True,
                        "is_recommended": not any_preferred
                    })
                
                added_ids = {m["id"] for m in models}
                
                for cfg in configs_list:
                    if not cfg.model:
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
            return models

    def _create_default_llm_config(self, workspace_id: UUID, user_id: UUID, is_preferred: bool) -> LLMConfig:
        """Helper to create the default system LLM config object"""
        return LLMConfig(
            id=UUID("00000000-0000-0000-0000-000000000000"),
            workspace_id=workspace_id,
            user_id=user_id,
            provider=configs.llm.provider,
            model=configs.llm.model_name,
            api_key="built-in",
            api_url=configs.llm.base_url,
            is_preferred=is_preferred
        )
