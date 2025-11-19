"""MCP JSON Config Example - Claude Desktop Format"""
import asyncio
import sys
import logging
import io
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).parent.parent))

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

logging.getLogger("root").setLevel(logging.ERROR)

from tools.mcp_client import create_client, create_mcp_config, mcp_config_to_connections
from llms.llm_manager import LLMManager
from common.config import LlmConfigs

# Claude Desktop compatible JSON config
MCP_CONFIG = {
    "mcpServers": {
        "oasm-platform": {
            "url": "http://localhost:3000/api/mcp",
            "headers": {
                "api-key": "8zV20IaGzatzSXKEAPr3m7ddnArDhT3cjnvr"
            }
        },
        "searxng": {
            "command": "npx",
            "args": ["-y", "mcp-searxng"],
            "env": {
                "SEARXNG_URL": "http://localhost:8080"
            }
        }
    }
}

WORKSPACE_ID = UUID("60191626-07c4-4f45-9e97-4f48c40a4626")
USER_ID = UUID("452d9b97-8754-4970-86ce-9cd3d4bb8356")


async def main():
    print("=" * 70)
    print("  MCP JSON Config Demo (Claude Desktop Format)")
    print("=" * 70)

    # Create MCPConfig instance
    mcp_config = create_mcp_config(MCP_CONFIG, WORKSPACE_ID, USER_ID)
    print(f"\n📦 Config: {len(mcp_config.servers)} servers")
    for name in mcp_config.list_server_names():
        print(f"   - {name}")

    # Convert to MCPConnection objects
    servers = mcp_config_to_connections(mcp_config)
    print(f"\n🔄 Converted to {len(servers)} connections")

    # Connect and test each server
    results = []
    for server in servers:
        print(f"\n[{server.name}]")
        async with create_client(server) as client:
            tools = await client.list_tools()
            print(f"  ✓ Connected - {len(tools)} tools")
            if tools:
                # Call first tool that matches common patterns
                for tool in tools:
                    if any(kw in tool['name'].lower() for kw in ['asset', 'search', 'list']):
                        args = {}
                        if 'workspaceId' in str(tool.get('input_schema', {})):
                            args['workspaceId'] = str(WORKSPACE_ID)
                        elif 'query' in str(tool.get('input_schema', {})):
                            args['query'] = 'test'

                        result = await client.call_tool(tool['name'], args)
                        results.append({
                            'server': server.name,
                            'tool': tool['name'],
                            'result': result
                        })
                        print(f"  ✓ Tested: {tool['name']}")
                        break

    # Show summary
    print(f"\n{'=' * 70}")
    print(f"[SUMMARY] {len(results)} successful calls")
    print("=" * 70)

    # Use LLM if we have results
    if len(results) >= 2:
        llm = LLMManager(config=LlmConfigs()).get_llm()
        response = await llm.ainvoke(f"""
Dựa vào kết quả từ {len(results)} MCP servers:
{results}

Tóm tắt ngắn gọn những gì có được.
""")
        print(response.content)

    print("\n[DONE]")


if __name__ == "__main__":
    asyncio.run(main())
