"""
Devicetree parsing tools.

Preferred: parse build_dir/zephyr/edt.pickle (best fidelity) if python modules are available.
Fallback: parse zephyr.dts text for basic node/status information.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from zephyr_mcp.core.workspace import resolve_workspace


def _ok(data: Any) -> dict:
    return {"ok": True, "error": None, "data": data}


def _err(message: str, *, hint: Optional[str] = None, type_: str = "Error") -> dict:
    return {"ok": False, "error": {"type": type_, "message": message, "hint": hint}, "data": None}


def _parse_dts_okay_nodes(dts_path: Path, max_nodes: int = 500) -> List[dict]:
    nodes: List[dict] = []
    try:
        lines = dts_path.read_text(errors="replace").splitlines()
    except OSError:
        return nodes
    for i, line in enumerate(lines, start=1):
        if 'status = "okay"' in line:
            nodes.append({"line": i, "text": line.strip()})
            if len(nodes) >= max_nodes:
                break
    return nodes


def parse_devicetree(
    workspace_root: Optional[str] = None,
    start_path: Optional[str] = None,
    build_dir: Optional[str] = None,
    dts_path: Optional[str] = None,
) -> dict:
    """
    Parse devicetree (best effort).

    Inputs:
    - build_dir: a west build directory containing zephyr/zephyr.dts and/or zephyr/edt.pickle
    - dts_path: explicit path to a DTS file (if not using build_dir)
    """
    try:
        ws = resolve_workspace(workspace_root=workspace_root, start_path=start_path or build_dir or dts_path)

        dts: Optional[Path] = None
        edt_pickle: Optional[Path] = None

        if build_dir:
            bdir = Path(build_dir).expanduser()
            if not bdir.is_absolute():
                bdir = ws.root / bdir
            bdir = bdir.resolve()
            # enforce workspace-local build dirs
            bdir.relative_to(ws.root.resolve())
            dts = bdir / "zephyr" / "zephyr.dts"
            edt_pickle = bdir / "zephyr" / "edt.pickle"
        elif dts_path:
            dts = Path(dts_path).expanduser().resolve()

        backend = "dts_text"
        data: Dict[str, Any] = {
            "workspace_root": str(ws.root),
            "zephyr_base": str(ws.zephyr_base),
            "build_dir": str(build_dir) if build_dir else None,
            "dts_path": str(dts) if dts else None,
            "edt_pickle": str(edt_pickle) if edt_pickle else None,
        }

        # Try edt.pickle if available and modules can be imported.
        if edt_pickle and edt_pickle.exists():
            try:
                import pickle

                # edt.pickle content is a pickled EDT object from Zephyr.
                # We intentionally keep this output summarized to avoid huge payloads.
                with edt_pickle.open("rb") as f:
                    edt = pickle.load(f)
                # EDT has nodes attribute (mapping), but structure can vary by Zephyr version.
                node_count = getattr(edt, "node_count", None)
                if node_count is None:
                    nodes = getattr(edt, "nodes", None)
                    node_count = len(nodes) if nodes is not None else None
                backend = "edt_pickle"
                data["summary"] = {"node_count": node_count}
                return _ok(data | {"backend": backend})
            except (OSError, pickle.UnpicklingError, AttributeError, ValueError, ModuleNotFoundError):
                # Fall back to dts text parsing below.
                pass

        if dts and dts.exists():
            ok_nodes = _parse_dts_okay_nodes(dts)
            return _ok(data | {"backend": backend, "enabled_nodes": ok_nodes, "enabled_count": len(ok_nodes)})

        return _err("No devicetree input found", hint="Pass build_dir (preferred) or dts_path.", type_="NotFound")
    except ValueError as e:
        return _err(str(e))

