"""MCP Integration Example: OASM + SearXNG"""
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

from tools.mcp_client import create_client
from data.database.models import MCPServer
from llms.llm_manager import LLMManager
from common.config import LlmConfigs

WORKSPACE_ID = UUID("60191626-07c4-4f45-9e97-4f48c40a4626")

mcp_oasm = MCPServer(
    workspace_id=WORKSPACE_ID,
    user_id=WORKSPACE_ID,
    mcp_config={
        "name": "oasm",
        "transport_type": "sse",
        "url": "http://localhost:3000/api/mcp",
        "headers": {"api-key": "8zV20IaGzatzSXKEAPr3m7ddnArDhT3cjnvr"}
    }
)

mcp_searxng = MCPServer(
    workspace_id=WORKSPACE_ID,
    user_id=WORKSPACE_ID,
    mcp_config={
        "name": "searxng",
        "transport_type": "stdio",
        "command": "npx",
        "args": ["-y", "mcp-searxng"],
        "env": {"SEARXNG_URL": "http://localhost:8080"}
    }
)


async def get_assets():
    async with create_client(mcp_oasm) as client:
        tools = await client.list_tools()
        tool = next((t['name'] for t in tools if 'asset' in t['name'].lower()), None)
        return await client.call_tool(tool, {"workspaceId": str(WORKSPACE_ID)}) if tool else None


async def get_threats():
    async with create_client(mcp_searxng) as client:
        tools = await client.list_tools()
        tool = next((t['name'] for t in tools if 'search' in t['name'].lower()), None)
        return await client.call_tool(tool, {"query": "web application security threats 2025"}) if tool else None


async def main():
    print("=" * 70)
    print("  OASM Assistant - MCP Integration Demo")
    print("=" * 70)

    assets = await get_assets()
    print(f"\n[1] Assets: {'✓' if assets else '✗'}")

    threats = await get_threats()
    print(f"[2] Threats: {'✓' if threats else '✗'}")

    if assets and threats:
        llm = LLMManager(config=LlmConfigs()).get_llm()
        response = await llm.ainvoke(f"""
Dựa vào: ASSETS={assets}, THREATS={threats}
Trả lời ngắn gọn: Số assets? Mối đe dọa? Khuyến nghị?
""")
        print(f"\n{'='*70}\n[LLM ANALYSIS]\n{'='*70}")
        print(response.content)
        print("=" * 70)

    print("\n[DONE]")


if __name__ == "__main__":
    asyncio.run(main())
