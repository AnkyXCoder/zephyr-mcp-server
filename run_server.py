"""
Entry point for Zephyr AI Platform MCP Server
"""

from zephyr_ai.core.server import create_server

if __name__ == "__main__":
    server = create_server()
    server.run()
