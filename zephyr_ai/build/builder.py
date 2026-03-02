import asyncio

from zephyr_ai.core.utils import build_subprocess_env


async def build(board: str, path: str, pristine: bool = True):
    """
    Build Zephyr application with optional pristine build.
    """
    cmd = ["west", "build", "-b", board, path]

    if pristine:
        cmd.append("--pristine")

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=build_subprocess_env(),
    )
    stdout, stderr = await process.communicate()

    return {
        "command": " ".join(cmd),
        "returncode": process.returncode,
        "stdout": stdout.decode(),
        "stderr": stderr.decode(),
    }
