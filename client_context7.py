from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

import asyncio
import json
import logging
import os
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


# -------------------------
# Logging
# -------------------------
logging.basicConfig(
    level=logging.WARNING,  # only warnings, errors, critical
    format="%(levelname)s:%(name)s:%(message)s",
)


# -------------------------
# Config
# -------------------------
API_KEY = os.environ.get("CONTEXT7_API_KEY")
if not API_KEY:
    raise RuntimeError("Environment variable CONTEXT7_API_KEY is not set")

MCP_URL = "https://mcp.context7.com/mcp"


def pretty(obj):
    try:
        return json.dumps(obj, indent=2, ensure_ascii=False)
    except Exception:
        return repr(obj)


async def main():
    # Instead of creating a custom httpx client here with headers,
    # rely on streamablehttp_client defaults and set environment variable
    os.environ["HTTPX_CLIENT_DEFAULT_HEADERS"] = json.dumps({
        "Authorization": f"Bearer {API_KEY}"
    })

    async with streamable_http_client(
        url=MCP_URL
    ) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            print("Connected to Context7 MCP", file=sys.stderr)

            await session.initialize()
            print("MCP session initialized", file=sys.stderr)

            tools_response = await session.list_tools()
            print("\nTools exposed by Context7:")
            for tool in tools_response.tools:
                print(f"- {tool.name}", file=sys.stderr)

            if not tools_response.tools:
                print("No tools available.",file=sys.stderr)
                return

            first_tool = tools_response.tools[0]
            # result = await session.call_tool(name=first_tool.name, arguments={})
            result = await session.call_tool(
                name=first_tool.name,
                arguments={"libraryName": "react"}
            )
            print("\nTool response:", file=sys.stderr)
            print(pretty(result.model_dump()))


if __name__ == "__main__":
    asyncio.run(main())
