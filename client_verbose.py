import asyncio
import os
import json
from contextlib import AsyncExitStack
import logging
import sys

# -------------------------
# Vertex AI Imports
# -------------------------
import vertexai
from vertexai.generative_models import (
    GenerativeModel,
    Tool,
    FunctionDeclaration,
    Part,
)

# -------------------------
# MCP Imports
# -------------------------
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# =========================================================
# Logging setup
# =========================================================
logging.basicConfig(level=logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(name)s:%(message)s")
handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(formatter)

mcp_logger = logging.getLogger("mcp.wire")
mcp_logger.setLevel(logging.DEBUG)
mcp_logger.addHandler(handler)
mcp_logger.propagate = False


# =========================================================
# MCP pretty printer (OBJECT-AWARE)
# =========================================================
def pretty_mcp_message(obj):
    """
    Converts MCP SessionMessage / JSONRPCMessage objects
    into readable, pretty-printed JSON.
    """
    try:
        # SessionMessage(message=..., metadata=...)
        if hasattr(obj, "message"):
            return json.dumps(
                {
                    "message": json.loads(pretty_mcp_message(obj.message)),
                    "metadata": obj.metadata,
                },
                indent=2,
                ensure_ascii=False,
            )

        # JSONRPCMessage(root=...)
        if hasattr(obj, "root"):
            return pretty_mcp_message(obj.root)

        # JSONRPCRequest / JSONRPCResponse
        if hasattr(obj, "__dict__"):
            return json.dumps(obj.__dict__, indent=2, ensure_ascii=False)

    except Exception:
        pass

    return repr(obj)


# =========================================================
# Logging Stream Reader (FULL MCP COMPATIBILITY)
# =========================================================
class LoggingStreamReader:
    def __init__(self, reader, logger, name="reader"):
        self._reader = reader
        self._logger = logger
        self.name = name

    # async context manager
    async def __aenter__(self):
        if hasattr(self._reader, "__aenter__"):
            await self._reader.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if hasattr(self._reader, "__aexit__"):
            return await self._reader.__aexit__(exc_type, exc, tb)
        return False

    # async iterator (CRITICAL)
    def __aiter__(self):
        self._aiter = self._reader.__aiter__()
        return self

    async def __anext__(self):
        msg = await self._aiter.__anext__()
        pretty = pretty_mcp_message(msg)
        self._logger.debug(f"[{self.name}] READ (MCP):\n{pretty}")
        return msg

    # delegate everything else
    def __getattr__(self, item):
        return getattr(self._reader, item)


# =========================================================
# Logging Stream Writer
# =========================================================
class LoggingStreamWriter:
    def __init__(self, writer, logger, name="writer"):
        self._writer = writer
        self._logger = logger
        self.name = name

    async def __aenter__(self):
        if hasattr(self._writer, "__aenter__"):
            await self._writer.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if hasattr(self._writer, "__aexit__"):
            return await self._writer.__aexit__(exc_type, exc, tb)
        return False

    def write(self, data):
        try:
            text = data.decode("utf-8", errors="replace")
            parsed = json.loads(text)
            pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
            self._logger.debug(f"[{self.name}] WRITE (JSON):\n{pretty}")
        except Exception:
            self._logger.debug(f"[{self.name}] WRITE (RAW): {data!r}")

        return self._writer.write(data)

    async def drain(self):
        return await self._writer.drain()

    def close(self):
        return self._writer.close()

    def __getattr__(self, item):
        return getattr(self._writer, item)


# =========================================================
# Vertex AI setup
# =========================================================
KEY_PATH = "vertex-ai-sa.json"
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = KEY_PATH

with open(KEY_PATH) as f:
    project_id = json.load(f)["project_id"]

vertexai.init(project=project_id, location="asia-south1")


def mcp_tools_to_vertex_tool(mcp_tools):
    funcs = []
    for t in mcp_tools:
        funcs.append(
            FunctionDeclaration(
                name=t.name,
                description=t.description,
                parameters=t.inputSchema,
            )
        )
    return Tool(function_declarations=funcs)


# =========================================================
# Main logic
# =========================================================
async def run_chat():
    params = StdioServerParameters(
        command="python",
        args=["server.py"],
    )

    async with AsyncExitStack() as stack:
        print("🔌 Connecting to MCP Server...")

        raw_reader, raw_writer = await stack.enter_async_context(
            stdio_client(params)
        )

        reader = LoggingStreamReader(raw_reader, mcp_logger, "mcp->client")
        writer = LoggingStreamWriter(raw_writer, mcp_logger, "client->mcp")

        session = await stack.enter_async_context(ClientSession(reader, writer))
        await session.initialize()

        tools = await session.list_tools()
        print(f"🛠️  Found tools: {[t.name for t in tools.tools]}")

        vertex_tool = mcp_tools_to_vertex_tool(tools.tools)

        model = GenerativeModel(
            "gemini-2.5-flash",
            tools=[vertex_tool],
        )
        chat = model.start_chat()

        user_input = "add 10 and 30"
        print(f"\n👤 User: {user_input}")

        response = chat.send_message(user_input)
        part = response.candidates[0].content.parts[0]

        fn = part.function_call
        print(f"🤖 Gemini wants: {fn.name} {dict(fn.args)}")

        result = await session.call_tool(fn.name, dict(fn.args))
        output = result.content[0].text
        print(f"✅ MCP Result: {output}")

        final = chat.send_message(
            Part.from_function_response(fn.name, {"result": output})
        )
        print(f"🤖 Final Answer: {final.text}")


# =========================================================
# Entrypoint
# =========================================================
if __name__ == "__main__":
    asyncio.run(run_chat())
