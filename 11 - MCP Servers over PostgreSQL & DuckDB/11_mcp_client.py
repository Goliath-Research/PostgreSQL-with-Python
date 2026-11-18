import asyncio
import os
from pathlib import Path
import sys

from pydantic import AnyUrl
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def smoke(fixture=True):
    env = dict(os.environ)
    if fixture:
        env.pop("COURSE_MCP_DATABASE_URL", None)
    server = Path(__file__).with_name("11_mcp_server.py").resolve()
    params = StdioServerParameters(command=sys.executable, args=[str(server)], env=env)
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            tools = {tool.name for tool in (await session.list_tools()).tools}
            uri = "schema://commerce/reporting"
            resource = await session.read_resource(AnyUrl(uri))
            lookup = await session.call_tool("get_order_summary", {"order_id": 101})
            rollup = await session.call_tool("get_category_sales", {"start_date": "2026-01-01", "end_date": "2026-01-03", "limit": 1})
            invalid = await session.call_tool("get_order_summary", {"order_id": -1})
            return tools, resource, lookup, rollup, invalid


if __name__ == "__main__":
    async def main():
        async with asyncio.timeout(30):
            tools, resource, lookup, rollup, invalid = await smoke(fixture="--postgres" not in sys.argv)
        print("Tools:", sorted(tools))
        for result in (resource, lookup, rollup, invalid):
            print(result.model_dump_json(exclude_none=True))
        if lookup.isError or rollup.isError or not invalid.isError:
            raise SystemExit("Unexpected tool outcomes")

    asyncio.run(main())
