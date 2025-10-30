"""
Integration test for MCP with langchain-mcp-adapters

This test verifies that the refactored MCP client/manager work correctly
with the langchain-mcp-adapters library.
"""

import asyncio
import sys
from pathlib import Path
from uuid import UUID

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add parent directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.mcp_client import create_client, create_manager
from data.database.models import MCPServer
from data.database import postgres_db


async def test_client_basic():
    """Test basic client functionality"""
    print("\n" + "="*70)
    print("TEST 1: Basic Client Functionality")
    print("="*70)

    # Create a test server (stdio - doesn't require real server)
    test_server = MCPServer(
        workspace_id=UUID("00000000-0000-0000-0000-000000000000"),
        user_id=UUID("00000000-0000-0000-0000-000000000000"),
        mcp_config={
            "name": "test_stdio",
            "display_name": "Test Stdio Server",
            "transport_type": "stdio",
            "command": "echo",
            "args": ["hello"],
            "is_active": True,
            "priority": 0
        }
    )

    try:
        async with create_client(test_server) as client:
            print(f"✅ Client created and connected")

            # Get info
            info = client.get_info()
            print(f"✅ Client info: {info}")

            # Check connection
            is_conn = await client.is_connected()
            print(f"✅ Is connected: {is_conn}")

            print("\n✅ Test 1 PASSED")
            return True

    except Exception as e:
        print(f"❌ Test 1 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_manager_basic():
    """Test basic manager functionality"""
    print("\n" + "="*70)
    print("TEST 2: Basic Manager Functionality")
    print("="*70)

    workspace_id = UUID("60191626-07c4-4f45-9e97-4f48c40a4626")
    user_id = UUID("60191626-07c4-4f45-9e97-4f48c40a4626")

    try:
        async with create_manager(postgres_db, workspace_id, user_id) as manager:
            print(f"✅ Manager created and initialized")

            # Get all info
            all_info = manager.get_all_info()
            print(f"✅ Found {len(all_info)} server(s)")

            for name, info in all_info.items():
                print(f"   - {name}: {info.get('display_name', 'N/A')}")

            # Get all tools
            all_tools = await manager.get_all_tools()
            print(f"✅ Total tools loaded from {len(all_tools)} server(s)")

            for server_name, tools in all_tools.items():
                print(f"   - {server_name}: {len(tools)} tool(s)")

            print("\n✅ Test 2 PASSED")
            return True

    except Exception as e:
        print(f"❌ Test 2 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_api_compatibility():
    """Test API backward compatibility"""
    print("\n" + "="*70)
    print("TEST 3: API Backward Compatibility")
    print("="*70)

    test_server = MCPServer(
        workspace_id=UUID("00000000-0000-0000-0000-000000000000"),
        user_id=UUID("00000000-0000-0000-0000-000000000000"),
        mcp_config={
            "name": "test_compat",
            "display_name": "Test Compatibility",
            "transport_type": "stdio",
            "command": "echo",
            "args": ["test"],
            "is_active": True,
            "priority": 0
        }
    )

    try:
        # Test all expected methods exist
        from tools.mcp_client import MCPClient
        client = MCPClient(test_server)

        expected_methods = [
            'connect', 'disconnect', 'list_tools', 'call_tool',
            'list_resources', 'read_resource', 'list_prompts',
            'get_prompt', 'is_connected', 'get_info'
        ]

        for method in expected_methods:
            assert hasattr(client, method), f"Missing method: {method}"
            print(f"   ✅ Method exists: {method}")

        print("\n✅ Test 3 PASSED - All API methods present")
        return True

    except Exception as e:
        print(f"❌ Test 3 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all integration tests"""
    print("\n")
    print("="*70)
    print(" MCP INTEGRATION TESTS - langchain-mcp-adapters")
    print("="*70)

    results = []

    # Run tests
    results.append(await test_api_compatibility())
    results.append(await test_client_basic())
    results.append(await test_manager_basic())

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Tests run: {len(results)}")
    print(f"Passed: {sum(results)}")
    print(f"Failed: {len(results) - sum(results)}")

    if all(results):
        print("\n✅ ALL TESTS PASSED")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
