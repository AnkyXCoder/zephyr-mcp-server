"""
Workspace / west tools exposed via MCP.
"""

from __future__ import annotations

import yaml
from typing import Any, Dict, List, Optional

from zephyr_ai.core.runner import make_zephyr_env, run_async
from zephyr_ai.core.workspace import detect_workspaces, resolve_workspace


def _ok(data: Any) -> dict:
    return {"ok": True, "error": None, "data": data}


def _err(message: str, *, hint: Optional[str] = None, type_: str = "Error") -> dict:
    return {"ok": False, "error": {"type": type_, "message": message, "hint": hint}, "data": None}


def detect_west_workspaces(start_paths: Optional[List[str]] = None) -> dict:
    """
    Detect west workspaces from the given start paths and optional env hints.
    """
    return _ok({"workspaces": detect_workspaces(start_paths)})


def analyze_workspace(workspace_root: Optional[str] = None, start_path: Optional[str] = None) -> dict:
    """
    Return normalized workspace info (root, zephyr base, manifest path).
    """
    try:
        ws = resolve_workspace(workspace_root=workspace_root, start_path=start_path)
        return _ok(ws.as_dict())
    except ValueError as e:
        return _err(str(e), hint="Pass workspace_root explicitly or run from inside a west workspace.")


def get_zephyr_version(workspace_root: Optional[str] = None, start_path: Optional[str] = None) -> dict:
    """
    Read Zephyr VERSION file from ZEPHYR_BASE.
    """
    try:
        ws = resolve_workspace(workspace_root=workspace_root, start_path=start_path)
        ver_file = ws.zephyr_base / "VERSION"
        if not ver_file.exists():
            return _err(f"VERSION file not found at: {ver_file}", type_="NotFound")
        txt = ver_file.read_text(errors="replace").strip()
        return _ok(
            {
                "zephyr_base": str(ws.zephyr_base),
                "version_file": str(ver_file),
                "raw": txt,
            }
        )
    except ValueError as e:
        return _err(str(e))


async def parse_west_manifest(workspace_root: Optional[str] = None, start_path: Optional[str] = None) -> dict:
    """
    Parse west manifest via `west manifest --resolve -o -`.
    """
    try:
        ws = resolve_workspace(workspace_root=workspace_root, start_path=start_path)
        env = make_zephyr_env(zephyr_base=str(ws.zephyr_base), workspace_root=str(ws.root))
        res = await run_async(["west", "manifest", "--resolve"], cwd=str(ws.root), env=env, timeout_s=60)
        data: Dict[str, Any] = {"command": res.as_dict(), "manifest": None, "raw": None}
        if res.returncode != 0:
            return _err("west manifest failed", hint=res.stderr or res.stdout, type_="CommandError") | {"data": data}
        try:
            data["raw"] = res.stdout
            data["manifest"] = yaml.safe_load(res.stdout) or {}
        except yaml.YAMLError as e:
            return _err(f"Failed to parse manifest YAML: {e}", hint=res.stdout[:2000], type_="ParseError") | {"data": data}
        return _ok(data)
    except ValueError as e:
        return _err(str(e))


async def list_modules(workspace_root: Optional[str] = None, start_path: Optional[str] = None) -> dict:
    """
    List west projects (often used as 'modules') via `west list` and manifest JSON.
    """
    try:
        ws = resolve_workspace(workspace_root=workspace_root, start_path=start_path)
        env = make_zephyr_env(zephyr_base=str(ws.zephyr_base), workspace_root=str(ws.root))
        res = await run_async(["west", "manifest", "--resolve"], cwd=str(ws.root), env=env, timeout_s=60)
        if res.returncode != 0:
            return _err("west manifest failed", hint=res.stderr or res.stdout, type_="CommandError")
        manifest = yaml.safe_load(res.stdout) or {}
        projects = (manifest.get("manifest", {}) or {}).get("projects", []) or []
        # Normalize common fields.
        normalized = []
        for p in projects:
            normalized.append(
                {
                    "name": p.get("name"),
                    "path": str((ws.root / (p.get("path") or "")).resolve()) if p.get("path") else None,
                    "revision": p.get("revision"),
                    "url": p.get("url"),
                    "remote": p.get("remote"),
                    "groups": p.get("groups"),
                }
            )
        return _ok({"workspace_root": str(ws.root), "count": len(normalized), "projects": normalized})
    except yaml.YAMLError as e:
        return _err(f"Failed to parse manifest YAML: {e}", type_="ParseError")
    except ValueError as e:
        return _err(str(e))


async def analyze_west_workspace(workspace_root: Optional[str] = None, start_path: Optional[str] = None) -> dict:
    """
    High-level workspace summary: resolved roots + manifest projects count.
    """
    try:
        ws = resolve_workspace(workspace_root=workspace_root, start_path=start_path)
        env = make_zephyr_env(zephyr_base=str(ws.zephyr_base), workspace_root=str(ws.root))
        res = await run_async(["west", "manifest", "--resolve"], cwd=str(ws.root), env=env, timeout_s=60)
        if res.returncode != 0:
            return _err("west manifest failed", hint=res.stderr or res.stdout, type_="CommandError")
        manifest = yaml.safe_load(res.stdout) or {}
        projects = (manifest.get("manifest", {}) or {}).get("projects", []) or []
        return _ok(
            {
                "workspace": ws.as_dict(),
                "project_count": len(projects),
                "west": {"manifest_command": res.as_dict()},
            }
        )
    except yaml.YAMLError as e:
        return _err(f"Failed to parse manifest YAML: {e}", type_="ParseError")
    except ValueError as e:
        return _err(str(e))

