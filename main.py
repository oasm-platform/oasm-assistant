# MCP Integration
import asyncio
from uuid import UUID

from tools.mcp_client import MCPClient, create_client
from data.database.models import MCPServer


server = MCPServer(
    workspace_id=UUID("acd9ebd6-7465-412b-919f-f7e149d37c8f"),
    user_id=UUID("acd9ebd6-7465-412b-919f-f7e149d37c8f"),
    # mcp_config={
    #     "name": "oasm",
    #     "display_name": "OASM Platform",
    #     "transport_type": "sse",
    #     "url": "http://localhost:3000/api/mcp",
    #     "headers": {"mcp-api-key": "6Ci55KFIDiT7Dazdi4nOZm3tVFWadQY6Ismf"},
    #     "is_active": True,
    #     "priority": 0
    # }
    mcp_config={
        "name": "searxng",
        "transport_type": "stdio",
        "command": "npx",
        "args": ["-y", "mcp-searxng"],
        "env": {
            "SEARXNG_URL": "http://localhost:8080"
        }
    }
)


def main():
    async def run():
        async with create_client(server) as client:
            print(f"✓ Connected: {client.get_info()}")
            tools = await client.list_tools()
            resources = await client.list_resources()
            prompts = await client.list_prompts()
            print(f"Tools: {tools}")
            print(f"Resources: {resources}")
            print(f"Prompts: {prompts}")

    asyncio.run(run())

if __name__ == "__main__":
    main()
