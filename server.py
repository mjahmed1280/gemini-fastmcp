# server.py
from fastmcp import FastMCP

# 1. Name your server
mcp = FastMCP("My Math Server")

# 2. Define a tool using standard Python type hints
@mcp.tool()
def add_two_numbers(a: int, b: int) -> int:
    """Add two numbers together. Use this when the user asks for math."""
    print(f"Server says: I am adding {a} + {b}!") # Log to see it working
    return a + b

@mcp.tool()
def ahmeds_custom_algorithm(a: int, b: int) -> int:
    """This function retuns sum of sqauares and sum of numbers. Use this when the user asks for ahmed's custom algorithm."""
    print(f"Server says: Maths is mathing -> sqr{a} +sqr{b} + {a} +{b}!") # Log to see it working
    return a**2 + b**2 + a + b


# 3. Run the server
if __name__ == "__main__":
    mcp.run()