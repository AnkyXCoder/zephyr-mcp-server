"""
Main MCP Server definition.
Registers all tools across modules.
"""

from mcp.server.fastmcp import FastMCP

from zephyr_ai.analysis.cppcheck import run_cppcheck
from zephyr_ai.firmware.mcuboot import analyze_image

from zephyr_ai.tools.boards_tools import list_boards
from zephyr_ai.tools.build_info_tools import get_build_info
from zephyr_ai.tools.build_tools import (
    build,
    build_flash,
    build_flash_debug,
    debugserver_start,
    debugserver_status,
    debugserver_stop,
    flash,
)
from zephyr_ai.tools.device_console_tools import (
    rtt_log_start,
    rtt_log_status,
    rtt_log_stop,
    serial_log_start,
    serial_log_status,
    serial_log_stop,
    serial_send_command,
)
from zephyr_ai.tools.devicetree_tools import parse_devicetree
from zephyr_ai.tools.kconfig_tools import search_kconfig_symbol
from zephyr_ai.tools.twister_tools import run_twister
from zephyr_ai.tools.workspace_tools import (
    analyze_west_workspace,
    analyze_workspace,
    detect_west_workspaces,
    get_zephyr_version,
    list_modules,
    parse_west_manifest,
)


def debug_env():
    import sys
    import os

    return {
        "python": sys.executable,
        "zephyr_base": os.getenv("ZEPHYR_BASE"),
    }


def create_server():
    mcp = FastMCP("zephyr-ai-platform")

    # Environment Debug
    mcp.tool()(debug_env)

    # Workspace / west
    mcp.tool()(detect_west_workspaces)
    mcp.tool()(analyze_workspace)
    mcp.tool()(analyze_west_workspace)
    mcp.tool()(get_zephyr_version)
    mcp.tool()(parse_west_manifest)
    mcp.tool()(list_modules)

    # Boards
    mcp.tool()(list_boards)

    # Build / Flash / Debug
    mcp.tool()(build)
    mcp.tool()(flash)
    mcp.tool()(build_flash)
    mcp.tool()(debugserver_start)
    mcp.tool()(debugserver_status)
    mcp.tool()(debugserver_stop)
    mcp.tool()(build_flash_debug)

    # Device console
    mcp.tool()(serial_log_start)
    mcp.tool()(serial_log_status)
    mcp.tool()(serial_log_stop)
    mcp.tool()(serial_send_command)
    mcp.tool()(rtt_log_start)
    mcp.tool()(rtt_log_status)
    mcp.tool()(rtt_log_stop)

    # Build introspection
    mcp.tool()(get_build_info)

    # Config intelligence
    mcp.tool()(search_kconfig_symbol)

    # Devicetree
    mcp.tool()(parse_devicetree)

    # Testing
    mcp.tool()(run_twister)

    # Analysis
    mcp.tool()(run_cppcheck)

    # Firmware
    mcp.tool()(analyze_image)

    return mcp


def main():
    """
    Console entrypoint for `zephyr-ai-mcp`.
    """
    server = create_server()
    server.run()
