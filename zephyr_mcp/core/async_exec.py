"""
Async command execution engine for high-performance build operations.
"""

import asyncio
from typing import Dict, List, Optional

from zephyr_mcp.core.utils import build_subprocess_env


async def run_async_command(
    cmd: List[str], *, cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None
) -> dict:
    """
    Executes subprocess asynchronously.
    """

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env=env or build_subprocess_env(),
    )

    stdout, stderr = await process.communicate()

    return {
        "command": " ".join(cmd),
        "returncode": process.returncode,
        "stdout": stdout.decode(),
        "stderr": stderr.decode()
    }
