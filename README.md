# MCP-Test Project

## Overview

This project demonstrates a client-server architecture where a Python server exposes custom tools using the `fastmcp` library. A separate client connects to this server, integrates with Google's Vertex AI Gemini model, and intelligently calls the server's tools based on natural language prompts.

The example showcases how to bridge local Python functions with a powerful language model, allowing the model to leverage your custom code to answer questions or perform tasks.

## Features

- **Tool Server:** A `fastmcp` server (`server.py`) that defines and exposes custom Python functions as tools.
  - `add_two_numbers(a: int, b: int)`: Adds two integers.
  - `ahmeds_custom_algorithm(a: int, b: int)`: A custom function that calculates the sum of squares and the sum of two numbers.
- **AI Client:** A client (`client.py`) that:
  - Connects to the local `fastmcp` server.
  - Fetches the list of available tools.
  - Integrates with the Vertex AI Gemini model (`gemini-2.5-flash`).
  - Passes the tools to the model and uses its function-calling capabilities to execute them based on a user prompt.
  - Sends the tool's output back to the model to generate a final, human-readable answer.

## Getting Started

### Prerequisites

- Python 3.7+
- A Google Cloud project with the Vertex AI API enabled.
- A service account with appropriate permissions for Vertex AI.

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd mcp-test
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Google Cloud Credentials:**
   - Obtain your service account JSON key file and rename it to `vertex-ai-sa.json`.
   - Place this file in the root of the `mcp-test` directory.
   - The `client.py` is pre-configured to load credentials from this file.

## Usage

The application consists of a server and a client that need to be run. The client will automatically start the server.

1. **Run the Client:**
   Open a terminal and run the client script:
   ```bash
   python client.py
   ```

2. **Follow the Output:**
   The client will:
   - Start and connect to the `server.py` process.
   - Discover the available tools (`add_two_numbers`, `ahmeds_custom_algorithm`).
   - Send a pre-defined prompt to the Gemini model.
   - The model will request to call one of the tools.
   - The client will execute the tool on the server and print the result.
   - The result is sent back to the model, which generates a final answer.

   Example output:
   ```
   🔌 Connecting to MCP Server...
   🛠️  Found tools: ['add_two_numbers', 'ahmeds_custom_algorithm']
   
   👤 User: what function are avialbe tvia mcp
   🤖 Gemini (Vertex) wants to call: ahmeds_custom_algorithm with {a: 2, b: 3}
   ✅ MCP Result: 22
   🤖 Final Answer: The result of Ahmed's custom algorithm with a=2 and b=3 is 22.
   ```

## How It Works

### Server (`server.py`)

- Uses `fastmcp` to create a simple server.
- The `@mcp.tool()` decorator exposes functions to any connected client.
- Each tool has a docstring that serves as its description, which the language model uses to decide when to call it.

### Client (`client.py`)

- Connects to the `fastmcp` server using a `StdioServerParameters` configuration, which means it runs the `server.py` script as a subprocess.
- It retrieves the list of tool definitions from the server.
- These definitions are converted into a format that the Vertex AI `GenerativeModel` can understand.
- When `chat.send_message()` is called, the model can choose to respond with text or with a `function_call` request.
- If it's a function call, the client executes it via the MCP session, captures the output, and sends it back to the model to complete the cycle.
