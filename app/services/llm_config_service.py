from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, update
from data.database import postgres_db 
from common.logger import logger
from data.database.models import LLMConfig
from common.config import configs
from llms import LLMManager

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
            async with self.db.get_session() as session:
                query = select(LLMConfig).filter(
                    LLMConfig.workspace_id == workspace_id,
                    LLMConfig.user_id == user_id
                )

                if search:
                    search_filter = f"%{search}%"
                    query = query.filter(LLMConfig.provider.ilike(search_filter))
                
                # Count
                from sqlalchemy import func
                count_query = select(func.count()).select_from(LLMConfig).filter(
                     LLMConfig.workspace_id == workspace_id,
                     LLMConfig.user_id == user_id
                )
                if search:
                    count_query = count_query.filter(LLMConfig.provider.ilike(search_filter))
                
                total_count_res = await session.execute(count_query)
                total_count = total_count_res.scalar()

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

                result = await session.execute(query)
                db_configs = result.scalars().all()
                db_configs = list(db_configs) # Convert to list

                # Inject default system config if configured and usable
                has_provider = bool(configs.llm.provider and configs.llm.model_name)
                is_usable = False
                if has_provider:
                    is_usable = bool(configs.llm.api_key or LLMManager.is_local_provider(configs.llm.provider))
                
                if has_provider and is_usable:
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
            async with self.db.get_session() as session:
                config = None
                if config_id:
                    # Update existing by ID
                    result = await session.execute(select(LLMConfig).filter(
                        LLMConfig.id == UUID(config_id),
                        LLMConfig.workspace_id == workspace_id,
                        LLMConfig.user_id == user_id
                    ))
                    config = result.scalars().first()
                
                if config and config.api_key == "built-in":
                    raise ValueError("Built-in system models cannot be modified")
                
                if not config:
                     # Check if this is the first custom LLM for this user/workspace
                    from sqlalchemy import func
                    count_query = select(func.count()).select_from(LLMConfig).filter(
                         LLMConfig.workspace_id == workspace_id,
                         LLMConfig.user_id == user_id
                    )
                    count_res = await session.execute(count_query)
                    is_first = count_res.scalar() == 0

                     # Create NEW
                    config = LLMConfig(
                        workspace_id=workspace_id,
                        user_id=user_id,
                        provider=provider,
                        api_key=api_key,
                        model=model,
                        api_url=api_url,
                        is_preferred=is_first
                    )
                    session.add(config)
                else:
                    # Update existing
                    config.provider = provider 
                    
                    if api_key and not api_key.startswith("****"):
                        config.api_key = api_key
                    if model is not None:
                        config.model = model
                    # Only update api_url if a non-empty value is provided
                    if api_url:
                        config.api_url = api_url

                await session.flush()
                await session.commit()
                await session.refresh(config)
                return config
        except Exception as e:
            logger.error("Error updating LLM config: {}", e)
            raise

    async def delete_llm_config(self, workspace_id: UUID, user_id: UUID, config_id: str) -> bool:
        try:
            async with self.db.get_session() as session:
                result = await session.execute(select(LLMConfig).filter(
                    LLMConfig.id == UUID(config_id),
                    LLMConfig.workspace_id == workspace_id,
                    LLMConfig.user_id == user_id
                ))
                config = result.scalars().first()

                if not config:
                    return False
                
                if config.api_key == "built-in":
                     raise ValueError("Built-in system models cannot be deleted")

                was_preferred = config.is_preferred

                await session.delete(config)
                await session.flush()

                # If we just deleted the preferred one, try to set the next available as preferred
                if was_preferred:
                    from sqlalchemy import desc
                    next_result = await session.execute(select(LLMConfig).filter(
                        LLMConfig.workspace_id == workspace_id,
                        LLMConfig.user_id == user_id
                    ).order_by(desc(LLMConfig.updated_at)))
                    next_config = next_result.scalars().first()
                    if next_config:
                        next_config.is_preferred = True

                await session.commit()
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
                async with self.db.get_session() as session:
                    # Unset all preferred flags
                    await session.execute(
                        update(LLMConfig).where(
                            LLMConfig.workspace_id == workspace_id,
                            LLMConfig.user_id == user_id
                        ).values(is_preferred=False)
                    )
                    await session.commit()
                
                # Return the virtual default config with is_preferred=True
                return self._create_default_llm_config(workspace_id, user_id, is_preferred=True)

            async with self.db.get_session() as session:
                # First, unset all preferred flags for this user/workspace
                await session.execute(
                    update(LLMConfig).where(
                        LLMConfig.workspace_id == workspace_id,
                        LLMConfig.user_id == user_id
                    ).values(is_preferred=False)
                )
                
                # Then set the specified config as preferred
                result = await session.execute(select(LLMConfig).filter(
                    LLMConfig.id == UUID(config_id),
                    LLMConfig.workspace_id == workspace_id,
                    LLMConfig.user_id == user_id
                ))
                config = result.scalars().first()
                
                if not config:
                    raise ValueError(f"LLM config with id {config_id} not found")
                
                config.is_preferred = True
                await session.commit()
                await session.refresh(config)
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
            async with self.db.get_session() as session:
                result = await session.execute(select(LLMConfig).filter(
                    LLMConfig.workspace_id == workspace_id,
                    LLMConfig.user_id == user_id
                ))
                configs_list = result.scalars().all()
                
                # Check if any user config is preferred
                any_preferred = any(cfg.is_preferred for cfg in configs_list)
                
                # Add default model from .env if configured and usable
                has_provider = bool(configs.llm.provider and configs.llm.model_name)
                is_usable = False
                if has_provider:
                    is_usable = bool(configs.llm.api_key or LLMManager.is_local_provider(configs.llm.provider))

                if has_provider and is_usable:
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
