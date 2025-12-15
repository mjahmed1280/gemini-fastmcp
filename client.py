import asyncio
import os
import json
from contextlib import AsyncExitStack

# Vertex AI Imports (Standard for Service Accounts)
import vertexai
from vertexai.generative_models import (
    GenerativeModel,
    Tool,
    FunctionDeclaration,
    Part,
)

# MCP Imports
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# --- CONFIGURATION ---
KEY_PATH = "vertex-ai-sa.json"
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = KEY_PATH

# 1. Auto-detect Project ID from the JSON file to initialize Vertex AI
with open(KEY_PATH, "r") as f:
    creds = json.load(f)
    project_id = creds.get("project_id")

vertexai.init(project=project_id, location="asia-south1") 

# --- HELPER: CONVERT MCP TOOL TO VERTEX AI TOOL ---
def mcp_tools_to_vertex_tool(mcp_tools_list):
    """
    Wraps MCP tools into a Vertex AI 'Tool' object.
    """
    funcs = []
    for tool in mcp_tools_list:
        # Create a Vertex FunctionDeclaration for each tool
        func_decl = FunctionDeclaration(
            name=tool.name,
            description=tool.description,
            parameters=tool.inputSchema # MCP schema maps directly to Vertex parameters
        )
        funcs.append(func_decl)
    
    # Vertex requires functions to be wrapped in a Tool object
    return Tool(function_declarations=funcs)

async def run_chat():
    # 2. Connect to the local MCP Server (server.py)
    server_params = StdioServerParameters(
        command="python", 
        args=["server.py"], 
        env=None
    )

    async with AsyncExitStack() as stack:
        print("🔌 Connecting to MCP Server...")
        
        # CORRECTED LINES: Unpack the tuple into read/write streams
        read_stream, write_stream = await stack.enter_async_context(stdio_client(server_params))
        session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
        
        await session.initialize()

        # 3. List tools from MCP
        result = await session.list_tools()
        print(f"🛠️  Found tools: {[t.name for t in result.tools]}")

        # 4. Convert and Initialize Vertex AI Model
        vertex_tool = mcp_tools_to_vertex_tool(result.tools)
        
        model = GenerativeModel(
            "gemini-2.5-flash",
            tools=[vertex_tool] # Vertex expects a list of Tool objects
        )
        chat = model.start_chat()

        # --- CHAT LOOP ---
        user_input = "what function are avialbe tvia mcp"
        print(f"\n👤 User: {user_input}")

        # Send message
        response = chat.send_message(user_input)
        
        # Vertex AI Response handling
        # We look for a 'function_call' in the first part of the response
        try:
            part = response.candidates[0].content.parts[0]
        except IndexError:
            print("❌ No response content.")
            return

        if part.function_call:
            fn_call = part.function_call
            print(f"🤖 Gemini (Vertex) wants to call: {fn_call.name} with {fn_call.args}")

            # 5. Execute the tool via MCP
            # Note: Vertex args are a Map, we convert to standard dict
            args_dict = dict(fn_call.args) 
            mcp_result = await session.call_tool(fn_call.name, arguments=args_dict)
            
            tool_output = mcp_result.content[0].text
            print(f"✅ MCP Result: {tool_output}")

            # 6. Send result back to Vertex AI
            # Vertex requires a specific 'Part' object for function responses
            response_part = Part.from_function_response(
                name=fn_call.name,
                response={"result": tool_output} 
            )
            
            final_response = chat.send_message(response_part)
            print(f"🤖 Final Answer: {final_response.text}")
        else:
            print(f"🤖 Gemini: {response.text}")

if __name__ == "__main__":
    asyncio.run(run_chat())