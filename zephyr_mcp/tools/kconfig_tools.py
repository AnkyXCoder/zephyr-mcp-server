"""
Kconfig symbol search tools.

Preferred: kconfiglib if installed.
Fallback: scan Kconfig* files under ZEPHYR_BASE.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, List, Optional

from zephyr_mcp.core.workspace import resolve_workspace


def _ok(data: Any) -> dict:
    return {"ok": True, "error": None, "data": data}


def _err(message: str, *, hint: Optional[str] = None, type_: str = "Error") -> dict:
    return {"ok": False, "error": {"type": type_, "message": message, "hint": hint}, "data": None}


def _scan_kconfig_files(zephyr_base: Path, symbol: str, max_hits: int = 200) -> List[dict]:
    hits: List[dict] = []
    s = symbol.strip()
    # Users often pass CONFIG_FOO while Kconfig defines "config FOO".
    bare = s[len("CONFIG_") :] if s.startswith("CONFIG_") else s
    pats = [
        re.compile(rf"\b{re.escape(s)}\b"),
        re.compile(rf"\b{re.escape(bare)}\b"),
        re.compile(rf"^\s*(menu)?config\s+{re.escape(bare)}\b"),
    ]
    for root, _, files in os.walk(zephyr_base):
        for fn in files:
            if not fn.startswith("Kconfig"):
                continue
            p = Path(root) / fn
            try:
                lines = p.read_text(errors="ignore").splitlines()
            except OSError:
                continue
            for idx, line in enumerate(lines, start=1):
                if any(p.search(line) for p in pats):
                    hits.append({"file": str(p), "line": idx, "text": line.strip()})
                    if len(hits) >= max_hits:
                        return hits
    return hits


def search_kconfig_symbol(
    symbol: str,
    workspace_root: Optional[str] = None,
    start_path: Optional[str] = None,
    max_hits: int = 200,
) -> dict:
    """
    Search Kconfig for a symbol reference/definition.
    """
    try:
        ws = resolve_workspace(workspace_root=workspace_root, start_path=start_path)
        hits = _scan_kconfig_files(ws.zephyr_base, symbol, max_hits=max_hits)
        return _ok(
            {
                "workspace_root": str(ws.root),
                "zephyr_base": str(ws.zephyr_base),
                "symbol": symbol,
                "count": len(hits),
                "hits": hits,
                "backend": "scan",
            }
        )
    except ValueError as e:
        return _err(str(e))

