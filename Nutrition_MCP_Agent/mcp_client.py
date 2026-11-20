
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER_PATH = Path(__file__).resolve().parent / "mcp_server.py"


@asynccontextmanager
async def connect_mcp():
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_PATH)],
        cwd=str(SERVER_PATH.parent)
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def discover_tools():
    async with connect_mcp() as session:
        result = await session.list_tools()

        return [
            {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.inputSchema
            }
            for tool in result.tools
        ]


async def call_mcp_tool(tool_name, arguments):
    async with connect_mcp() as session:
        result = await session.call_tool(
            tool_name,
            arguments=arguments
        )

        output = "\n".join(
            item.text
            for item in result.content
            if item.type == "text"
        )

        if result.isError:
            raise RuntimeError(output or "MCP tool failed")

        return output
