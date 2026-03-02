"""
Build introspection tools.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from zephyr_ai.core.workspace import resolve_workspace


def _ok(data: Any) -> dict:
    return {"ok": True, "error": None, "data": data}


def _err(message: str, *, hint: Optional[str] = None, type_: str = "Error") -> dict:
    return {"ok": False, "error": {"type": type_, "message": message, "hint": hint}, "data": None}


def _file_info(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        st = path.stat()
        return {"path": str(path), "size": st.st_size, "mtime": st.st_mtime}
    except OSError:
        return {"path": str(path)}


def get_build_info(build_dir: str, workspace_root: Optional[str] = None) -> dict:
    """
    Summarize a west build directory.
    """
    try:
        ws = resolve_workspace(workspace_root=workspace_root, start_path=build_dir)
        bdir = Path(build_dir).expanduser()
        if not bdir.is_absolute():
            bdir = ws.root / bdir
        bdir = bdir.resolve()
        # enforce workspace-local build dirs
        bdir.relative_to(ws.root.resolve())

        zephyr_dir = bdir / "zephyr"
        info = {
            "workspace_root": str(ws.root),
            "zephyr_base": str(ws.zephyr_base),
            "build_dir": str(bdir),
            "files": {
                "CMakeCache.txt": _file_info(bdir / "CMakeCache.txt"),
                "runners.yaml": _file_info(zephyr_dir / "runners.yaml"),
                ".config": _file_info(zephyr_dir / ".config"),
                "zephyr.elf": _file_info(zephyr_dir / "zephyr.elf"),
                "zephyr.hex": _file_info(zephyr_dir / "zephyr.hex"),
                "zephyr.bin": _file_info(zephyr_dir / "zephyr.bin"),
                "zephyr.dts": _file_info(zephyr_dir / "zephyr.dts"),
                "edt.pickle": _file_info(zephyr_dir / "edt.pickle"),
            },
        }

        # best-effort config snippet
        cfg = zephyr_dir / ".config"
        if cfg.exists():
            try:
                lines = cfg.read_text(errors="replace").splitlines()
                snippet = "\n".join(lines[:200])
                info["config_head"] = snippet
            except OSError:
                pass

        return _ok(info)
    except ValueError as e:
        return _err(str(e))

