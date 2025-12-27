from typing import Dict, Tuple, List, Optional, Any
from uuid import UUID
import threading
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

from data.database import postgres_db
from data.database.models import MCPConfig
from tools.mcp_client import MCPManager
from common.logger import logger
from common.config import configs
from sqlalchemy.orm.attributes import flag_modified

class MCPServerService:
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

    def _initialize_manager(self, manager: MCPManager) -> None:
        """Initialize manager if not already initialized"""
        if not manager._initialized:
            try:
                self._run_async(manager.initialize())
            except Exception as e:
                logger.warning("Manager initialization failed: {}", e)

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

    def _validate_server_config(self, server_config: dict) -> bool:
        """Validate that server has required transport config"""
        return "url" in server_config or "command" in server_config

    async def _get_server_status(self, manager: MCPManager, server_name: str, test_connection: bool = True) -> Tuple[bool, Optional[str]]:
        """Get actual server status by checking manager state"""
        return await manager.get_server_status(server_name, test_connection=test_connection)

    async def _enrich_config_with_status(self, config: MCPConfig, manager: MCPManager, skip_health_check: bool = False, include_tools: bool = False) -> Dict[str, Any]:
        """
        Enrich MCP config with live status for each server.
        Returns dict with active/status/error fields for each server.
        
        Args:
            config: MCP configuration
            manager: MCP manager instance
            skip_health_check: If True, skip actual connection test (faster, uses cached state)
            include_tools: If True, fetch tools and resources for active servers
        """
        enriched_servers = {}

        # Ensure manager is initialized
        self._initialize_manager(manager)

        for name, server_config in config.servers.items():
            # Use fast check by default (no actual connection test)
            is_active, error = await self._get_server_status(manager, name, test_connection=not skip_health_check)
            
            enriched_server = dict(server_config)
            enriched_server["active"] = is_active
            
            # Determine status: active > disabled > error
            if is_active:
                enriched_server["status"] = "active"
                # Only fetch tools and resources if explicitly requested
                if include_tools:
                    try:
                        tools = self._run_async(manager.get_tools(name, apply_filter=False))
                        resources = self._run_async(manager.get_resources(name))
                        enriched_server["tools"] = tools
                        enriched_server["resources"] = resources
                    except Exception as e:
                        logger.warning("Failed to enrich details for {}: {}", name, e)
                        enriched_server["tools"] = []
                        enriched_server["resources"] = []
                else:
                    # Provide empty arrays when not fetching
                    enriched_server["tools"] = []
                    enriched_server["resources"] = []
            elif server_config.get("disabled"):
                enriched_server["status"] = "disabled"
            else:
                enriched_server["status"] = "error"
            
            if error:
                enriched_server["error"] = error
            
            enriched_servers[name] = enriched_server
            
        return {"mcpServers": enriched_servers}

    async def _build_response_dict(self, config: MCPConfig, manager: MCPManager, skip_health_check: bool = False, include_tools: bool = False) -> Dict[str, Any]:
        """Build response dict with metadata and enriched servers"""
        enriched_config = await self._enrich_config_with_status(config, manager, skip_health_check=skip_health_check, include_tools=include_tools)
        config_metadata = config.to_dict()
        
        return {
            "id": str(config_metadata["id"]),
            "workspace_id": str(config_metadata["workspace_id"]),
            "user_id": str(config_metadata["user_id"]),
            "created_at": config_metadata["created_at"],
            "updated_at": config_metadata["updated_at"],
            "mcpServers": enriched_config["mcpServers"]
        }

    async def get_server_config(self, workspace_id: UUID, user_id: UUID, skip_health_check: bool = False, include_tools: bool = False) -> Dict[str, Any]:
        """Get MCP configuration with status
        
        Args:
            workspace_id: Workspace ID
            user_id: User ID
            skip_health_check: If False, performs actual connection test (default: False for accuracy)
            include_tools: If True, fetch tools and resources (default: False for performance)
        """
        with self.db.get_session() as session:
            config = self._get_or_create_config(session, workspace_id, user_id)
            manager = self._get_manager(workspace_id, user_id)
            return await self._build_response_dict(config, manager, skip_health_check=skip_health_check, include_tools=include_tools)

    async def add_servers(self, workspace_id: UUID, user_id: UUID, servers: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Add servers to configuration
        Returns: (success, error_message, updated_config_dict)
        """
        with self.db.get_session() as session:
            config = self._get_or_create_config(session, workspace_id, user_id)
            
            successful_adds = False
            errors = []

            for server_name, server_config in servers.items():
                if not self._validate_server_config(server_config):
                    errors.append(f"{server_name}: must have 'url' or 'command'")
                    continue

                if server_name in config.servers:
                    errors.append(f"{server_name}: already exists")
                    continue

                try:
                    config.add_server(server_name, server_config)
                    successful_adds = True
                except Exception as e:
                    errors.append(f"{server_name}: {str(e)}")

            if successful_adds:
                session.commit()
                session.refresh(config)
                
                # Reinitialize manager
                manager = self._get_manager(workspace_id, user_id)
                self._initialize_manager(manager)
                
                # Include tools and resources in response for UI display
                return True, None, await self._build_response_dict(config, manager, skip_health_check=True, include_tools=True)
            
            return False, "; ".join(errors) if errors else "No servers added", None

    async def update_servers(self, workspace_id: UUID, user_id: UUID, servers: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Update servers in configuration (REPLACES entire config)
        Returns: (success, error_message, updated_config_dict)
        """        
        with self.db.get_session() as session:
            config = self._get_or_create_config(session, workspace_id, user_id)
                    
            # Validate all servers first
            errors = []
            for server_name, server_config in servers.items():
                if not self._validate_server_config(server_config):
                    errors.append(f"{server_name}: must have 'url' or 'command'")
            
            if errors:
                return False, "; ".join(errors), None
            
            # REPLACE entire config (clear old servers and add new ones)
            config.config_json["mcpServers"] = {}
            flag_modified(config, "config_json")  # Mark as modified for SQLAlchemy
            
            for server_name, server_config in servers.items():
                try:
                    config.add_server(server_name, server_config)
                except Exception as e:
                    logger.error("Failed to add server {}: {}", server_name, e)
                    errors.append(f"{server_name}: {str(e)}")
            
            if errors:
                # Rollback if any server failed
                session.rollback()
                return False, "; ".join(errors), None
            
            session.commit()
            session.refresh(config)
            
            # Force re-initialize manager to reload new config
            manager = self._get_manager(workspace_id, user_id)
            self._run_async(manager.initialize())  # Force reload
            
            # Include tools and resources in response for UI display
            return True, None, await self._build_response_dict(config, manager, skip_health_check=True, include_tools=True)

    def delete_config(self, config_id: str, workspace_id: UUID, user_id: UUID) -> Tuple[bool, str]:
        """
        Delete entire MCP configuration
        Returns: (success, message)
        """
        try:
            config_uuid = UUID(config_id)
        except ValueError:
            return False, "Invalid config ID format"

        with self.db.get_session() as session:
            config = session.query(MCPConfig).filter(
                MCPConfig.id == config_uuid,
                MCPConfig.workspace_id == workspace_id,
                MCPConfig.user_id == user_id
            ).first()

            if not config:
                return False, f"MCP Config with ID {config_id} not found"

            server_count = len(config.servers)
            session.delete(config)
            session.commit()

            # Reinitialize manager to clear connections
            manager = self._get_manager(workspace_id, user_id)
            self._initialize_manager(manager)
            
            return True, f"Successfully deleted MCP config with {server_count} server(s)"

    async def get_server_health(self, workspace_id: UUID, user_id: UUID, server_name: str) -> tuple[bool, str, Optional[str]]:
        """
        Get health status of a specific MCP server
        Returns: (is_active: bool, status: str, error_message: Optional[str])
        """
        manager = self._get_manager(workspace_id, user_id)
        self._initialize_manager(manager)
        
        is_active, error = await self._get_server_status(manager, server_name, test_connection=True)
        
        # Determine status
        if is_active:
            status = "active"
        elif error and "disabled" in error.lower():
            status = "disabled"
        else:
            status = "error"
        
        return is_active, status, error

    def cleanup(self):
        """Cleanup resources"""
        try:
            for manager in self._managers.values():
                try:
                    self._run_async(manager.shutdown())
                except Exception as e:
                    logger.error("Error shutting down manager: {}", e)

            if self._async_loop and self._async_loop.is_running():
                self._async_loop.call_soon_threadsafe(self._async_loop.stop)

            if self._executor:
                self._executor.shutdown(wait=True)

            logger.info("MCPServerService cleanup completed")
        except Exception as e:
            logger.error("Error during cleanup: {}", e)
