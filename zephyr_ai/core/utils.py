"""
Utility helpers for command execution and response formatting.
"""

import os
import subprocess
import sys
from typing import Dict, List, Optional


def build_subprocess_env(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """
    Create a subprocess environment that prefers the MCP server's interpreter environment.

    We prepend the directory of `sys.executable` to PATH so tools installed in that
    environment (e.g., west/pre-commit) are found first.
    """
    env = dict(os.environ)
    py_bin_dir = os.path.dirname(sys.executable)
    if py_bin_dir:
        env["PATH"] = py_bin_dir + os.pathsep + env.get("PATH", "")
    if extra:
        env.update(extra)
    return env


def run_command(cmd: List[str], *, cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None):
    """
    Executes a subprocess command safely and returns structured result.
    """

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env or build_subprocess_env(),
        check=False,
    )

    return {
        "command": " ".join(cmd),
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr
    }
