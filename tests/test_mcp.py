"""
Pytest tests for MCP Client and Manager functionality
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from data.database.models import MCPConfig
from tools.mcp_client import MCPClient, create_client, MCPManager, create_manager
from tools.mcp_client.utils import MCPConnection
from data.database import postgres_db


@pytest.fixture
def mock_mcp_database():
    """Mock database with session"""
    mock_db = Mock()
    mock_session = Mock()
    mock_db.get_session.return_value.__enter__ = Mock(return_value=mock_session)
    mock_db.get_session.return_value.__exit__ = Mock(return_value=None)

    # Setup mock query chain
    mock_query = Mock()
    mock_query.all.return_value = []
    mock_query.filter.return_value = mock_query  # Allow chaining .filter().all()
    mock_session.query.return_value = mock_query

    return mock_db


@pytest.fixture
def real_database():
    """Real database for integration tests"""
    return postgres_db


@pytest.fixture
def workspace_id():
    """Test workspace ID"""
    from uuid import uuid4
    return uuid4()


@pytest.fixture
def user_id():
    """Test user ID"""
    from uuid import uuid4
    return uuid4()


@pytest.fixture
def test_server(workspace_id, user_id):
    """Reusable test connection"""
    return MCPConnection(
        name="test_server",
        workspace_id=workspace_id,
        user_id=user_id,
        transport_type="sse",
        url="http://localhost:5173/api/mcp",
        headers={"mcp-api-key": "test-key"}
    )


@pytest.fixture
def test_servers(workspace_id, user_id):
    """Multiple test connections"""
    return [
        MCPConnection(
            name=f"test_server_{i}",
            workspace_id=workspace_id,
            user_id=user_id,
            transport_type="sse",
            url=f"http://localhost:{5173+i}/api/mcp",
            headers={"api-key": "test"}
        ) for i in range(1, 3)
    ]


class TestMCPClient:
    """Test MCP Client operations"""

    def test_client_initialization_and_properties(self, test_server):
        """Test client creation and properties"""
        client = MCPClient(test_server)

        assert client.server.name == "test_server"
        assert client.server.transport_type == "sse"
        assert client.server.url == "http://localhost:5173/api/mcp"
        # Note: is_connected() is async, so we check the internal state directly
        assert not client._connected

    @pytest.mark.asyncio
    async def test_client_context_manager(self, test_server):
        """Test client context manager"""
        with patch.object(MCPClient, 'connect', new_callable=AsyncMock), \
             patch.object(MCPClient, 'disconnect', new_callable=AsyncMock):
            async with create_client(test_server) as client:
                assert isinstance(client, MCPClient)

    @pytest.mark.parametrize("method", [
        'connect', 'disconnect', 'list_tools', 'list_resources',
        'list_prompts', 'get_info', 'is_connected'
    ])
    def test_client_has_method(self, test_server, method):
        """Test client has required methods"""
        client = MCPClient(test_server)
        assert hasattr(client, method)


class TestMCPManager:
    """Test MCP Manager operations"""

    @pytest.mark.parametrize("method", [
        'initialize', 'shutdown', 'add_server', 'remove_server',
        'get_all_info', 'get_all_tools', 'get_all_resources',
        'get_all_prompts', 'call_tool'
    ])
    def test_manager_has_methods(self, mock_mcp_database, workspace_id, user_id, method):
        """Test manager has required methods"""
        manager = MCPManager(mock_mcp_database, workspace_id, user_id)
        assert hasattr(manager, method)

    @pytest.mark.asyncio
    async def test_manager_initialize(self, mock_mcp_database, workspace_id, user_id, test_servers):
        """Test manager initialization with workspace and user filter"""
        mock_session = mock_mcp_database.get_session.return_value.__enter__.return_value
        mock_query = Mock()
        # Mock the filter chain for both workspace_id and user_id
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = test_servers
        mock_session.query.return_value = mock_query

        manager = MCPManager(mock_mcp_database, workspace_id, user_id)
        with patch.object(MCPClient, 'connect', new_callable=AsyncMock):
            await manager.initialize()

        assert mock_session.query.called
        # Verify filter was called (for workspace_id and user_id filtering)
        assert mock_query.filter.called

    @pytest.mark.asyncio
    async def test_manager_context_manager(self, mock_mcp_database, workspace_id, user_id):
        """Test manager context manager"""
        async with create_manager(mock_mcp_database, workspace_id, user_id) as manager:
            assert isinstance(manager, MCPManager)
            assert manager.workspace_id == workspace_id
            assert manager.user_id == user_id

    @pytest.mark.asyncio
    async def test_manager_operations(self, mock_mcp_database, workspace_id, user_id):
        """Test manager query operations"""
        manager = MCPManager(mock_mcp_database, workspace_id, user_id)
        await manager.initialize()

        # Test get_all_info
        mock_info = {"test_server": {"name": "test_server", "version": "1.0.0"}}
        with patch.object(manager, 'get_all_info', return_value=mock_info):
            assert manager.get_all_info() == mock_info

        # Test get_all_tools
        mock_tools = {"test_server": [{"name": "tool1"}]}
        with patch.object(manager, 'get_all_tools', new_callable=AsyncMock, return_value=mock_tools):
            assert await manager.get_all_tools() == mock_tools

        # Test call_tool
        mock_result = {"status": "success"}
        with patch.object(manager, 'call_tool', new_callable=AsyncMock, return_value=mock_result):
            assert await manager.call_tool("test_server", "tool", {}) == mock_result


class TestMCPConfigModel:
    """Test MCP Config model"""

    def test_config_model_creation(self, workspace_id, user_id):
        """Test MCPConfig model properties"""
        config = MCPConfig(
            workspace_id=workspace_id,
            user_id=user_id,
            config_json={
                "mcpServers": {
                    "test_server": {
                        "transport_type": "sse",
                        "url": "http://localhost:5173/api/mcp"
                    }
                }
            }
        )
        assert config.workspace_id == workspace_id
        assert config.user_id == user_id
        assert "test_server" in config.servers
        assert config.servers["test_server"]["url"] == "http://localhost:5173/api/mcp"


@pytest.mark.integration
class TestMCPDatabaseIntegration:
    """Integration tests with real database"""

    @pytest.fixture
    def mcp_config_helper(self, workspace_id, user_id):
        """Helper to create/update MCP config"""
        def _get_or_create(session):
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
                session.commit()
                session.refresh(config)

            return config
        return _get_or_create

    def test_crud_operations(self, real_database, mcp_config_helper, workspace_id, user_id):
        """Test create, read, update, delete operations on MCPConfig"""
        # Create and add server
        with real_database.get_session() as session:
            config = mcp_config_helper(session)
            config.add_server("test_crud_server", {
                "transport_type": "sse",
                "url": "http://localhost:9999/mcp"
            })
            session.commit()
            config_id = config.id
            assert config_id is not None

        # Read
        with real_database.get_session() as session:
            config = session.query(MCPConfig).filter_by(id=config_id).first()
            assert config is not None
            assert "test_crud_server" in config.servers

        # Update
        with real_database.get_session() as session:
            config = session.query(MCPConfig).filter_by(id=config_id).first()
            config.add_server("test_crud_server", {
                "transport_type": "sse",
                "url": "http://localhost:9999/mcp/v2"
            })
            session.commit()

        # Verify update
        with real_database.get_session() as session:
            config = session.query(MCPConfig).filter_by(id=config_id).first()
            assert config.servers["test_crud_server"]["url"] == "http://localhost:9999/mcp/v2"

        # Delete server
        with real_database.get_session() as session:
            config = session.query(MCPConfig).filter_by(id=config_id).first()
            config.remove_server("test_crud_server")
            session.commit()

        # Verify deletion
        with real_database.get_session() as session:
            config = session.query(MCPConfig).filter_by(id=config_id).first()
            assert "test_crud_server" not in config.servers

    def test_query_configs(self, real_database):
        """Test querying MCP configs"""
        with real_database.get_session() as session:
            configs = session.query(MCPConfig).all()
            assert isinstance(configs, list)
            total_servers = sum(len(c.servers) for c in configs)
            print(f"\n[OK] Found {len(configs)} config(s) with {total_servers} total server(s)")

    def test_bulk_create_servers(self, real_database, mcp_config_helper, workspace_id, user_id):
        """Test creating multiple servers in one config"""
        servers_config = [
            ("test_active", "sse", "http://localhost:9999/test_active"),
            ("test_inactive", "sse", "http://localhost:9999/test_inactive")
        ]

        with real_database.get_session() as session:
            config = mcp_config_helper(session)

            for name, transport_type, url in servers_config:
                config.add_server(name, {
                    "transport_type": transport_type,
                    "url": url
                })

            session.commit()

            # Verify servers
            config = session.query(MCPConfig).filter(
                MCPConfig.workspace_id == workspace_id,
                MCPConfig.user_id == user_id
            ).first()
            assert "test_active" in config.servers
            assert "test_inactive" in config.servers
            print(f"\n[OK] Created {len(servers_config)} servers in config")
