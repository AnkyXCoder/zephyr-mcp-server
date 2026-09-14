"""
Entry point for Zephyr MCP Server
"""

from zephyr_mcp.core.server import create_server

if __name__ == "__main__":
    server = create_server()
    server.run()
