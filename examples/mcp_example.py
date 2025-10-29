"""
OASM Assistant - Main Entry Point
Example: LLM calls 2 MCPs (OASM + SearXNG)
"""
import asyncio
import sys
from pathlib import Path
from uuid import UUID

# Add parent directory to sys.path to import modules from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.mcp_client import create_client
from data.database.models import MCPServer
from llms.llm_manager import LLMManager
from common.config import LlmConfigs

# MCP 1: OASM Platform
mcp_oasm = MCPServer(
    workspace_id=UUID("60191626-07c4-4f45-9e97-4f48c40a4626"),
    user_id=UUID("60191626-07c4-4f45-9e97-4f48c40a4626"),
    mcp_config={
        "name": "oasm",
        "display_name": "OASM Platform",
        "transport_type": "sse",
        "url": "http://localhost:3000/api/mcp",
        "headers": {"api-key": "8zV20IaGzatzSXKEAPr3m7ddnArDhT3cjnvr"},
        "is_active": True,
        "priority": 0
    }
)

# MCP 2: SearXNG Search
mcp_searxng = MCPServer(
    workspace_id=UUID("60191626-07c4-4f45-9e97-4f48c40a4626"),
    user_id=UUID("60191626-07c4-4f45-9e97-4f48c40a4626"),
    mcp_config={
        "name": "searxng",
        "display_name": "SearXNG Search",
        "transport_type": "stdio",
        "command": "npx",
        "args": ["-y", "mcp-searxng"],
        "env": {"SEARXNG_URL": "http://localhost:8080"},
        "is_active": True,
        "priority": 1
    }
)

llm_manager = LLMManager(config=LlmConfigs())


async def main():
    """Main entry point - LLM calls both MCPs"""

    print("=" * 70)
    print("  OASM Assistant - 2 MCPs Integration")
    print("=" * 70)

    # Connect to OASM MCP
    print("\n[1] Connecting to OASM MCP...")
    async with create_client(mcp_oasm) as oasm_client:
        tools = await oasm_client.list_tools()
        asset_tool = next((t['name'] for t in tools if 'asset' in t['name'].lower()), None)

        if asset_tool:
            assets = await oasm_client.call_tool(
                name=asset_tool,
                args={"workspaceId": str(mcp_oasm.workspace_id)}
            )
            print(f"[OK] Got assets from OASM")
        else:
            assets = None
            print("[ERROR] No asset tool found")

    # Connect to SearXNG MCP
    print("\n[2] Connecting to SearXNG MCP...")
    async with create_client(mcp_searxng) as search_client:
        tools = await search_client.list_tools()
        search_tool = next((t['name'] for t in tools if 'search' in t['name'].lower()), None)

        if search_tool:
            threats = await search_client.call_tool(
                name=search_tool,
                args={"query": "web application security threats 2025"}
            )
            print(f"[OK] Got threat info from SearXNG")
        else:
            threats = None
            print("[ERROR] No search tool found")

    # LLM analyzes both
    if assets and threats:
        print("\n[3] LLM analyzing data from both MCPs...")
        llm = llm_manager.get_llm()
        print("assets: ", assets)
        print("threats: ", threats)
        prompt = f"""Dựa vào 2 nguồn dữ liệu:

1. ASSETS: {str(assets)}
2. THREATS: {str(threats)}

Trả lời ngắn gọn:
- Có bao nhiêu assets?
- Mối đe dọa nào liên quan?
- Khuyến nghị gì?
"""

        response = await llm.ainvoke(prompt)

        print("\n" + "=" * 70)
        print("[ANSWER]")
        print("=" * 70)
        print(response.content)
        print("=" * 70)

    print("\n[DONE]")


if __name__ == "__main__":
    asyncio.run(main())
