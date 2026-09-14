"""
Utility helpers for command execution and response formatting.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional


def build_subprocess_env(workspace_root: Optional[str] = None, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """
    Create a subprocess environment that prefers a workspace venv (if found),
    then the MCP server's interpreter environment, then the existing PATH.
    """
    env = dict(os.environ)

    venv_bin: Optional[str] = None
    if workspace_root:
        start = Path(workspace_root).expanduser().resolve()
        if start.is_file():
            start = start.parent
        for candidate_dir in [start, *start.parents]:
            for venv_name in (".venv", "venv", "env"):
                candidate_bin = candidate_dir / venv_name / "bin"
                if (candidate_bin / "west").exists() or (candidate_bin / "python").exists():
                    venv_bin = str(candidate_bin)
                    break
            if venv_bin:
                break

    path_parts = []
    if venv_bin:
        path_parts.append(venv_bin)
    py_bin_dir = os.path.dirname(sys.executable)
    if py_bin_dir:
        path_parts.append(py_bin_dir)
    path_parts.append(env.get("PATH", ""))
    env["PATH"] = os.pathsep.join(p for p in path_parts if p)
    if venv_bin:
        env["VIRTUAL_ENV"] = str(Path(venv_bin).parent)

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
        env=env or build_subprocess_env(workspace_root=cwd),
        check=False,
    )

    return {
        "command": " ".join(cmd),
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr
    }
