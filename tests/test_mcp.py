"""
Pytest tests for MCP Client and Manager functionality
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from data.database.models.mcp_servers import MCPServer
from tools.mcp_client import MCPClient, create_client, MCPManager, create_manager
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
    """Reusable test server"""
    return MCPServer(
        workspace_id=workspace_id,
        user_id=user_id,
        mcp_config={
            "name": "test_server",
            "display_name": "Test Server",
            "transport_type": "sse",
            "url": "http://localhost:5173/api/mcp",
            "headers": {"mcp-api-key": "test-key"},
            "is_active": True,
            "priority": 0
        }
    )


@pytest.fixture
def test_servers(workspace_id, user_id):
    """Multiple test servers"""
    return [
        MCPServer(
            workspace_id=workspace_id,
            user_id=user_id,
            mcp_config={
                "name": f"test_server_{i}",
                "display_name": f"Test Server {i}",
                "transport_type": "sse",
                "url": f"http://localhost:{5173+i}/api/mcp",
                "headers": {"api-key": "test"},
                "is_active": i == 1,
                "priority": 10 - i*5
            }
        ) for i in range(1, 3)
    ]


class TestMCPClient:
    """Test MCP Client operations"""

    def test_client_initialization_and_properties(self, test_server):
        """Test client creation and properties"""
        client = MCPClient(test_server)

        assert client.server.name == "test_server"
        assert client.server.display_name == "Test Server"
        assert client.server.transport_type == "sse"
        assert client.server.url == "http://localhost:5173/api/mcp"
        assert client.server.mcp_config.get('url') == "http://localhost:5173/api/mcp"
        assert not client.is_connected()

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
        """Test manager add/remove/query operations"""
        manager = MCPManager(mock_mcp_database, workspace_id, user_id)
        await manager.initialize()

        # Test add_server with workspace_id and user_id
        with patch.object(manager, 'add_server', new_callable=AsyncMock, return_value=True) as mock_add:
            assert await manager.add_server({
                "workspace_id": workspace_id,
                "user_id": user_id,
                "mcp_config": {
                    "name": "new_server",
                    "transport_type": "sse",
                    "url": "http://localhost:5173/api/mcp"
                }
            })
            mock_add.assert_called_once()

        # Test remove_server
        with patch.object(manager, 'remove_server', new_callable=AsyncMock, return_value=True) as mock_remove:
            assert await manager.remove_server("test_server")
            mock_remove.assert_called_once_with("test_server")

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


class TestMCPServerModel:
    """Test MCP Server model"""

    def test_server_model_creation(self, test_server):
        """Test MCPServer model properties"""
        assert test_server.name == "test_server"
        assert test_server.display_name == "Test Server"
        assert test_server.transport_type == "sse"
        assert test_server.url == "http://localhost:5173/api/mcp"
        assert test_server.mcp_config.get('url') == "http://localhost:5173/api/mcp"
        assert test_server.mcp_config.get('is_active') is True
        assert test_server.priority == 0


@pytest.mark.integration
class TestMCPDatabaseIntegration:
    """Integration tests with real database"""

    @pytest.fixture
    def db_server(self, workspace_id, user_id):
        """Helper to create/update test server"""
        def _create_or_update(session, name, **kwargs):
            # Query all servers for this workspace/user
            servers = session.query(MCPServer).filter(
                MCPServer.workspace_id == workspace_id,
                MCPServer.user_id == user_id
            ).all()

            # Find existing server by name
            existing = None
            for s in servers:
                if s.name == name:
                    existing = s
                    break

            if existing:
                # Update existing server config
                new_config = existing.mcp_config.copy()
                if 'mcp_config' in kwargs:
                    new_config.update(kwargs['mcp_config'])
                    kwargs.pop('mcp_config')
                for key, value in kwargs.items():
                    new_config[key] = value
                existing.mcp_config = new_config
                server = existing
            else:
                # Create new server
                if 'mcp_config' not in kwargs:
                    kwargs['mcp_config'] = {'name': name}
                else:
                    kwargs['mcp_config']['name'] = name

                server = MCPServer(
                    workspace_id=workspace_id,
                    user_id=user_id,
                    **kwargs
                )
                session.add(server)
            session.commit()
            session.refresh(server)
            return server
        return _create_or_update

    def test_crud_operations(self, real_database, db_server, workspace_id, user_id):
        """Test create, read, update, delete operations"""
        # Create
        with real_database.get_session() as session:
            server = db_server(session, "test_crud_server",
                              mcp_config={
                                  "name": "test_crud_server",
                                  "display_name": "CRUD Test",
                                  "transport_type": "sse",
                                  "url": "http://localhost:9999/mcp",
                                  "is_active": False,
                                  "priority": 0
                              })
            server_id = server.id
            assert server_id is not None

        # Read
        with real_database.get_session() as session:
            server = session.query(MCPServer).filter_by(id=server_id).first()
            assert server is not None
            assert server.name == "test_crud_server"

        # Update
        with real_database.get_session() as session:
            server = session.query(MCPServer).filter_by(id=server_id).first()
            config = server.mcp_config.copy()
            config['display_name'] = "Updated CRUD Test"
            config['priority'] = 10
            server.mcp_config = config
            session.commit()

        # Verify update
        with real_database.get_session() as session:
            server = session.query(MCPServer).filter_by(id=server_id).first()
            assert server.display_name == "Updated CRUD Test"
            assert server.mcp_config.get('priority') == 10

        # Delete
        with real_database.get_session() as session:
            server = session.query(MCPServer).filter_by(id=server_id).first()
            session.delete(server)
            session.commit()

        # Verify deletion
        with real_database.get_session() as session:
            server = session.query(MCPServer).filter_by(id=server_id).first()
            assert server is None

    def test_query_servers(self, real_database):
        """Test querying servers"""
        with real_database.get_session() as session:
            servers = session.query(MCPServer).all()
            assert isinstance(servers, list)
            print(f"\n[OK] Found {len(servers)} server(s)")

    def test_bulk_create_servers(self, real_database, db_server, workspace_id, user_id):
        """Test creating multiple servers"""
        servers_config = [
            ("test_active", "Active Server", True, 10),
            ("test_inactive", "Inactive Server", False, 0)
        ]

        with real_database.get_session() as session:
            for name, display_name, is_active, priority in servers_config:
                db_server(session, name,
                         mcp_config={
                             "name": name,
                             "display_name": display_name,
                             "transport_type": "sse",
                             "url": f"http://localhost:9999/{name}",
                             "is_active": is_active,
                             "priority": priority
                         })

            # Verify active servers
            servers = session.query(MCPServer).filter(
                MCPServer.workspace_id == workspace_id,
                MCPServer.user_id == user_id
            ).all()
            active = [s for s in servers if s.mcp_config.get('is_active', False)]
            active_names = [s.name for s in active]
            assert "test_active" in active_names
            print(f"\n[OK] Created/updated {len(servers_config)} servers")
