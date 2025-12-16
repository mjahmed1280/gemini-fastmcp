# client_main.py
import asyncio
import os
import json
import logging
import sys
from dotenv import load_dotenv

# Vertex AI imports
import vertexai
from vertexai.generative_models import (
    GenerativeModel,
    Tool,
    FunctionDeclaration,
    Part,
)

# MCP imports
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

# Load .env if present
load_dotenv()

# -----------------------------
# Logging
# -----------------------------
logging.basicConfig(level=logging.WARNING, format="%(levelname)s:%(name)s:%(message)s")

# -----------------------------
# Config
# -----------------------------
CONTEXT7_API_KEY = os.environ.get("CONTEXT7_API_KEY")
if not CONTEXT7_API_KEY:
    raise RuntimeError("Environment variable CONTEXT7_API_KEY is not set")

KEY_PATH = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "vertex-ai-sa.json")
if not os.path.exists(KEY_PATH):
    raise RuntimeError(f"Vertex service account JSON not found at: {KEY_PATH}")

# Set environment variable just like your legacy code did
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = KEY_PATH

with open(KEY_PATH, "r") as f:
    creds = json.load(f)
    project_id = creds.get("project_id")
if not project_id:
    raise RuntimeError("project_id missing in Vertex service account JSON")

vertexai.init(project=project_id, location="asia-south1")


MCP_URL = "https://mcp.context7.com/mcp"

# Helper to convert MCP JSON schema → Vertex compatible
def normalize_schema(mcp_schema: dict) -> dict:
    """
    Strip out unsupported fields (e.g. `additionalProperties`)
    and keep only type/properties/required.
    """
    if not isinstance(mcp_schema, dict):
        return {}

    schema = {}
    # Only copy fields Vertex supports:
    for key in ["type", "properties", "required"]:
        if key in mcp_schema:
            schema[key] = mcp_schema[key]

    # Normalize nested properties recursively
    if "properties" in schema:
        props = {}
        for pname, pval in schema["properties"].items():
            props[pname] = normalize_schema(pval)
        schema["properties"] = props

    return schema

# Convert MCP tools → Vertex Tool
def mcp_tools_to_vertex_tool(mcp_tools_list):
    decls = []
    for tool in mcp_tools_list:
        # build Vertex parameter schema
        params = {}
        if tool.inputSchema:
            # Convert MCP inputSchema schema dict (JSON-RPC) into Vertex parameters format
            params = {
                "type": "object",
                "properties": {},
                "required": []
            }
            for pname, pinfo in (tool.inputSchema.get("properties") or {}).items():
                params["properties"][pname] = normalize_schema(pinfo)
                # treat all properties as optional (Vertex accepts empty list)
            if not params["required"]:
                params.pop("required", None)

        decl = FunctionDeclaration(
            name=tool.name,
            description=(tool.description or ""),
            parameters=params if params else None
        )
        decls.append(decl)
    return Tool(function_declarations=decls)

def extract_part(response):
    try:
        return response.candidates[0].content.parts[0]
    except Exception:
        return None

# Main
async def main():
    # Set default headers for streamable_http_client
    os.environ["HTTPX_CLIENT_DEFAULT_HEADERS"] = json.dumps({
        "Authorization": f"Bearer {CONTEXT7_API_KEY}"
    })

    async with streamable_http_client(url=MCP_URL) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            print("Connected to Context7 MCP", file=sys.stderr)
            await session.initialize()

            # List Context7 tools
            tools_response = await session.list_tools()
            if not tools_response.tools:
                print("No tools from Context7", file=sys.stderr)
                return

            tool_names = [t.name for t in tools_response.tools]
            print("Context7 MCP tools:", tool_names, file=sys.stderr)

            # Wrap into Vertex AI tool
            vertex_tool = mcp_tools_to_vertex_tool(tools_response.tools)

            model = GenerativeModel(
                "gemini-2.5-flash",
                tools=[vertex_tool]
            )
            chat = model.start_chat()

            user_input = input("Enter query for MCP tools: ").strip()
            if not user_input:
                print("Empty input; exiting.")
                return

            response = chat.send_message(user_input)

            while True:
                part = extract_part(response)

                if part is None:
                    print("No response part")
                    break

                # 1️⃣ Gemini wants to call a tool
                if part.function_call:
                    fn = part.function_call
                    name = fn.name
                    args = dict(fn.args or {})

                    print(f"Gemini called `{name}` with {args}", file=sys.stderr)

                    mcp_result = await session.call_tool(name=name, arguments=args)

                    try:
                        output = mcp_result.content[0].text
                    except Exception:
                        output = json.dumps(mcp_result.model_dump(), indent=2)

                    # Send tool result back to Gemini
                    response = chat.send_message(
                        Part.from_function_response(
                            name=name,
                            response={"result": output}
                        )
                    )
                    continue  # 🔁 wait for next model step

                # 2️⃣ Gemini produced text — we are done
                if part.text:
                    # print("\nFinal Gemini answer:\n")
                    # print(part.text)
                    break

            if part.function_call:
                fn = part.function_call
                name = fn.name
                args = dict(fn.args or {})

                print(f"Gemini called tool `{name}` with args {args}", file=sys.stderr)

                mcp_result = await session.call_tool(name=name, arguments=args)
                try:
                    out = mcp_result.content[0].text
                except Exception:
                    out = json.dumps(mcp_result.model_dump(), indent=2, ensure_ascii=False)

                print("MCP tool output:", out, file=sys.stderr)

                # Send back as function response
                fr = Part.from_function_response(name=name, response={"result": out})
                final = chat.send_message(fr)
                print("\nFinal Gemini answer:\n")
                print(getattr(final, "text", None) or json.dumps(final.candidates[0].content.dict(), indent=2))
            else:
                print("\nGemini text reply:\n")
                print(getattr(response, "text", None) or json.dumps(response.candidates[0].content.dict(), indent=2))

if __name__ == "__main__":
    asyncio.run(main())
