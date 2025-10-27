"""
OASM Assistant - Main Entry Point
Example: LLM calls MCP to answer "How many assets in my workspace?"
"""
import asyncio
import sys
from uuid import UUID

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from tools.mcp_client import MCPClient, create_client
from data.database.models import MCPServer
from llms.llm_manager import LLMManager
from common.config import LlmConfigs
from common.logger import logger


mcp_server = MCPServer(
    workspace_id=UUID("a3d865ac-2413-42d4-a051-1f3641ce2356"),
    user_id=UUID("a3d865ac-2413-42d4-a051-1f3641ce2356"),
    mcp_config={
        "name": "oasm",
        "display_name": "OASM Platform",
        "transport_type": "sse",
        "url": "http://localhost:3000/api/mcp",
        "headers": {"api-key": "9AuzJUk57QVF6irnLVW20CALS5quPaz6SB7K"},
        "is_active": True,
        "priority": 0
    }
)


llm_config = LlmConfigs()
llm_manager = LLMManager(config=llm_config)


async def example_count_assets():
    """Example: LLM calls MCP to count assets in workspace"""

    print("\n" + "=" * 70)
    print("  Example: Workspace của tôi có bao nhiêu assets?")
    print("=" * 70)

    # Connect to MCP server
    print("\n[INFO] Connecting to MCP server...")
    async with create_client(mcp_server) as mcp_client:
        print(f"[OK] MCP Connected: {mcp_client.get_info()}")

        # List available tools
        tools = await mcp_client.list_tools()
        print(f"\n[TOOLS] Available MCP Tools ({len(tools)} tools):")
        for tool in tools:
            tool_name = tool.get('name', 'unknown')
            tool_desc = tool.get('description', 'No description')
            print(f"  - {tool_name}: {tool_desc}")

        # Find the correct tool name for getting assets
        asset_tool_name = None
        for tool in tools:
            name = tool.get('name', '').lower()
            if 'asset' in name:
                asset_tool_name = tool.get('name')
                break

        if not asset_tool_name:
            print("\n[ERROR] No asset-related tool found in MCP")
            print("Available tools:", [t.get('name') for t in tools])
            return

        # Call MCP tool to get assets
        print(f"\n[CALL] Calling MCP tool: {asset_tool_name}")
        workspace_id = str(mcp_server.workspace_id)
        print(f"[INFO] Using workspace ID: {workspace_id}")

        assets_result = await mcp_client.call_tool(
            name=asset_tool_name,
            args={"workspaceId": workspace_id}
        )

        if not assets_result:
            print("[ERROR] No assets found or MCP tool failed")
            return

        print(f"[OK] Retrieved assets data from MCP")

        # Step 2: Use LLM to analyze and answer the question
        print("\n[LLM] Using LLM to analyze assets...")

        # Get LLM instance
        llm = llm_manager.get_llm()

        # Create prompt for LLM
        prompt = f"""Dựa vào dữ liệu assets sau đây, hãy trả lời câu hỏi:
"Workspace của tôi có bao nhiêu assets?"

Dữ liệu từ MCP:
{str(assets_result)}

Hãy đưa ra câu trả lời ngắn gọn bằng tiếng Việt, bao gồm:
1. Tổng số assets
2. Phân loại theo loại (domain, IP, subdomain, web app, v.v.)
3. Phân tích mức độ rủi ro
4. Đề xuất hành động (nếu có)
"""

        # Call LLM
        response = await llm.ainvoke(prompt)

        print("\n" + "=" * 70)
        print("[ANSWER] LLM Answer:")
        print("=" * 70)
        print(response.content)
        print("=" * 70)


def main():
    """Main entry point"""

    print("=" * 70)
    print("  OASM Assistant - LLM + MCP Integration")
    print("=" * 70)

    # Check LLM configuration
    if llm_config.provider and llm_config.api_key:
        print(f"\n[OK] LLM Configured: {llm_config.provider}")
        if llm_config.model_name:
            print(f"   Model: {llm_config.model_name}")
    else:
        print("\n[WARNING] LLM not configured")
        print("   Set LLM_PROVIDER and LLM_API_KEY in .env file")
        print("   Available providers: openai, anthropic, google, ollama")

    # Run the example
    asyncio.run(example_count_assets())

    print("\n[DONE]")


if __name__ == "__main__":
    main()
