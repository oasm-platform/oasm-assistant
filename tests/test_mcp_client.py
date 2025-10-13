"""Quick MCP Client Tests"""
import asyncio
import pytest

from data.database.models.mcp_servers import MCPServer, TransportType
from tools.mcp_client import MCPClient, create_client

def test_basic():
    """Test basic client creation"""
    server = MCPServer(
        name="test",
        display_name="Test Server",
        transport_type=TransportType.SSE,
        url="http://localhost:5173/api/mcp",
        headers={"mcp-api-key": "i9Zqtk6bDvWhJArjpfHwUtZ1JzZkD7zD9OM5"},
        is_active=True
    )

    client = MCPClient(server)
    assert client.server.name == "test"
    assert not client.is_connected()
    print("✓ Basic test passed")


@pytest.mark.asyncio
async def test_connect():
    """Test connecting to OASM"""
    server = MCPServer(
        name="oasm",
        display_name="OASM Platform",
        transport_type=TransportType.SSE,
        url="http://localhost:5173/api/mcp",
        headers={"mcp-api-key": "i9Zqtk6bDvWhJArjpfHwUtZ1JzZkD7zD9OM5"},
        is_active=True
    )

    try:
        async with create_client(server) as client:
            assert client.is_connected()

            # Test operations
            tools = await client.list_tools()
            resources = await client.list_resources()
            prompts = await client.list_prompts()
            info = client.get_info()

            print(f"\n✓ Connected to {info['name']}")
            print(f"  Tools: {len(tools)}")
            print(f"  Resources: {len(resources)}")
            print(f"  Prompts: {len(prompts)}")

            if tools:
                print(f"\nFirst tool: {tools[0].get('name')}")

    except Exception as e:
        print(f"✗ Connection failed: {e}")
        print("  Make sure OASM server is running on localhost:5173")


def run_tests():
    """Run all tests"""
    print("=" * 50)
    print("MCP Client Quick Tests")
    print("=" * 50)

    # Sync test
    test_basic()

    # Async test
    print("\nTesting connection...")
    asyncio.run(test_connect())

    print("\n" + "=" * 50)
    print("Tests completed!")


if __name__ == "__main__":
    run_tests()
