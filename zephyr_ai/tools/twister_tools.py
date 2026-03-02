"""
Twister integration via west.

Runs `west twister` with optional args and captures a JSON report when possible.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, List, Optional

from zephyr_ai.core.runner import make_zephyr_env, run_async
from zephyr_ai.core.workspace import resolve_workspace


def _ok(data: Any) -> dict:
    return {"ok": True, "error": None, "data": data}


def _err(message: str, *, hint: Optional[str] = None, type_: str = "Error") -> dict:
    return {"ok": False, "error": {"type": type_, "message": message, "hint": hint}, "data": None}


async def run_twister(
    workspace_root: Optional[str] = None,
    start_path: Optional[str] = None,
    testsuite_root: Optional[str] = None,
    platform: Optional[str] = None,
    extra_args: Optional[List[str]] = None,
    timeout_s: Optional[float] = 1800,
) -> dict:
    """
    Run twister via west.

    If possible, enables a JSON report and returns a summary.
    """
    try:
        ws = resolve_workspace(workspace_root=workspace_root, start_path=start_path or testsuite_root)
        env = make_zephyr_env(zephyr_base=str(ws.zephyr_base))

        argv: List[str] = ["west", "twister"]
        if testsuite_root:
            argv.extend(["-T", testsuite_root])
        if platform:
            argv.extend(["-p", platform])

        with tempfile.TemporaryDirectory(prefix="zephyr_ai_twister_") as td:
            report_dir = Path(td)
            # Twister writes twister.json into the report dir.
            argv.extend(["-o", str(report_dir)])
            json_report_path = report_dir / "twister.json"

            if extra_args:
                argv.extend(extra_args)

            res = await run_async(argv, cwd=str(ws.root), env=env, timeout_s=timeout_s)

            report = None
            if json_report_path.exists():
                try:
                    report = json.loads(json_report_path.read_text(errors="replace"))
                except json.JSONDecodeError:
                    report = {"error": "failed_to_parse_json_report"}

            summary = None
            if isinstance(report, dict):
                # Common keys vary; keep it defensive.
                summary = {
                    "testsuites": report.get("testsuites") or report.get("test_suites"),
                    "tests": report.get("tests") or report.get("testcases"),
                    "status_counts": report.get("status_counts") or report.get("summary"),
                }

            return _ok(
                {
                    "workspace_root": str(ws.root),
                    "zephyr_base": str(ws.zephyr_base),
                    "command": res.as_dict(),
                    "json_report": report,
                    "summary": summary,
                }
            )
    except ValueError as e:
        return _err(str(e))
