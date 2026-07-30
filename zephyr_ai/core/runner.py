"""
Unified subprocess runner for MCP tools.

Goals:
- consistent env (MCP python environment first in PATH + ZEPHYR_BASE injection)
- consistent cwd (workspace root)
- structured results
- async-first (tools can await command execution)
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from zephyr_ai.core.utils import build_subprocess_env


@dataclass(frozen=True)
class CommandResult:
    command: List[str]
    returncode: int
    stdout: str
    stderr: str
    cwd: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "command": " ".join(self.command),
            "argv": list(self.command),
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "cwd": self.cwd,
        }


def make_zephyr_env(*, zephyr_base: Optional[str] = None, workspace_root: Optional[str] = None, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    env = build_subprocess_env(workspace_root=workspace_root)
    if zephyr_base:
        env["ZEPHYR_BASE"] = zephyr_base
    if extra:
        env.update(extra)
    return env


async def run_async(
    argv: List[str],
    *,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    timeout_s: Optional[float] = None,
) -> CommandResult:
    if not argv:
        raise ValueError("argv must be non-empty")

    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env=env,
    )

    try:
        if timeout_s is None:
            stdout_b, stderr_b = await proc.communicate()
        else:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except asyncio.TimeoutError:
        proc.kill()
        stdout_b, stderr_b = await proc.communicate()
        return CommandResult(
            command=argv,
            returncode=proc.returncode if proc.returncode is not None else -1,
            stdout=(stdout_b or b"").decode(errors="replace"),
            stderr=((stderr_b or b"").decode(errors="replace") + f"\nTimed out after {timeout_s}s").strip(),
            cwd=cwd,
        )

    return CommandResult(
        command=argv,
        returncode=proc.returncode or 0,
        stdout=(stdout_b or b"").decode(errors="replace"),
        stderr=(stderr_b or b"").decode(errors="replace"),
        cwd=cwd,
    )

