# server.py

from fastmcp import FastMCP, ToolError
import httpx
import os
import json
import sys
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file


mcp = FastMCP("My Math + Context7 Server")

# -----------------------------
# Local Math Tools
# -----------------------------
@mcp.tool()
def add_two_numbers(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b

@mcp.tool()
def ahmeds_custom_algorithm(a: int, b: int) -> int:
    """Returns sum of squares + sum."""
    return a**2 + b**2 + a + b

# -----------------------------
# Context7 Helper Tools
# -----------------------------
CONTEXT7_API_KEY = os.environ.get("CONTEXT7_API_KEY")
if not CONTEXT7_API_KEY:
    raise RuntimeError("Environment variable CONTEXT7_API_KEY is not set")

CONTEXT7_MCP_URL = "https://mcp.context7.com/mcp"

async def call_context7(name: str, arguments: dict):
    """
    Proxy a call to the Context7 MCP server.
    """
    headers = {
        "Authorization": f"Bearer {CONTEXT7_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": name,
            "arguments": arguments
        }
    }

    async with httpx.AsyncClient(timeout=None, headers=headers) as client:
        resp = await client.post(CONTEXT7_MCP_URL, json=payload)
        data = resp.json()

    # Check for errors in Context7 response
    if "error" in data:
        raise ToolError(f"Context7 MCP error: {data['error']}")

    return data["result"]

@mcp.tool()
async def context7_resolve_library_id(libraryName: str) -> dict:
    """
    Resolve a library name via Context7.
    """
    result = await call_context7("resolve-library-id", {"libraryName": libraryName})
    return result

@mcp.tool()
async def context7_get_library_docs(
    context7CompatibleLibraryID: str, topic: str = ""
) -> dict:
    """
    Get library docs from Context7, optionally by topic.
    """
    args = {"context7CompatibleLibraryID": context7CompatibleLibraryID}
    if topic:
        args["topic"] = topic
    result = await call_context7("get-library-docs", args)
    return result

if __name__ == "__main__":
    mcp.run()
