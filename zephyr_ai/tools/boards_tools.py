"""
Board and shield listing for Zephyr.

We avoid relying on `west boards` output format differences and instead scan:
- <ZEPHYR_BASE>/boards/**/board.yml
- <ZEPHYR_BASE>/boards/shields/**/shield.yml
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional

import yaml

from zephyr_ai.core.workspace import resolve_workspace


def _ok(data: Any) -> dict:
    return {"ok": True, "error": None, "data": data}


def _err(message: str, *, hint: Optional[str] = None, type_: str = "Error") -> dict:
    return {"ok": False, "error": {"type": type_, "message": message, "hint": hint}, "data": None}


def _read_yaml(path: Path) -> dict:
    try:
        with path.open("r", errors="replace") as f:
            data = yaml.safe_load(f) or {}
        return data if isinstance(data, dict) else {}
    except OSError:
        return {}


def _vendor_alias(filter_value: str) -> str:
    v = (filter_value or "").strip().lower()
    aliases = {
        "nordic": "nordic",
        "stm": "st",
        "st": "st",
        "nxp": "nxp",
        "espressif": "espressif",
        "esp": "espressif",
    }
    return aliases.get(v, v)


def _matches_filter(entry: dict, filter_value: Optional[str]) -> bool:
    if not filter_value:
        return True
    f = filter_value.strip().lower()
    if f == "shields":
        return entry.get("type") == "shield"
    if f.startswith("vendor:"):
        want = f.split("vendor:", 1)[1].strip()
        return (entry.get("vendor") or "").lower() == want.lower()
    want_vendor = _vendor_alias(f)
    return (entry.get("vendor") or "").lower() == want_vendor.lower()


def _scan_boards(zephyr_base: Path) -> List[dict]:
    boards_dir = zephyr_base / "boards"
    if not boards_dir.exists():
        return []

    results: List[dict] = []

    # Regular boards: boards/<vendor>/<board>/board.yml
    for yml in boards_dir.glob("*/*/board.yml"):
        data = _read_yaml(yml)
        vendor = data.get("vendor") or yml.parents[1].name
        name = data.get("name") or yml.parents[0].name
        full_name = data.get("full_name") or data.get("full-name")
        socs = data.get("socs") or []
        results.append(
            {
                "type": "board",
                "name": name,
                "full_name": full_name,
                "vendor": vendor,
                "yml": str(yml),
                "dir": str(yml.parent),
                "socs": socs,
            }
        )

    # Shields: boards/shields/<vendor>/<shield>/shield.yml (vendor sometimes acts as category)
    shields_dir = boards_dir / "shields"
    if shields_dir.exists():
        for yml in shields_dir.glob("*/*/shield.yml"):
            data = _read_yaml(yml)
            vendor = data.get("vendor") or yml.parents[1].name
            name = data.get("name") or yml.parents[0].name
            full_name = data.get("full_name") or data.get("full-name")
            results.append(
                {
                    "type": "shield",
                    "name": name,
                    "full_name": full_name,
                    "vendor": vendor,
                    "yml": str(yml),
                    "dir": str(yml.parent),
                }
            )

    return results


def list_boards(
    workspace_root: Optional[str] = None,
    start_path: Optional[str] = None,
    filter_by: Optional[str] = None,
) -> dict:
    """
    List boards and/or shields.

    Filter examples:
    - \"nordic\", \"st\", \"nxp\", \"esp\"\n
    - \"shields\"\n
    - \"vendor:nordic\"\n
    """
    try:
        ws = resolve_workspace(workspace_root=workspace_root, start_path=start_path)
        entries = _scan_boards(ws.zephyr_base)
        filtered = [e for e in entries if _matches_filter(e, filter_by)]
        return _ok(
            {
                "workspace_root": str(ws.root),
                "zephyr_base": str(ws.zephyr_base),
                "filter": filter_by,
                "count": len(filtered),
                "entries": filtered,
            }
        )
    except ValueError as e:
        return _err(str(e))

