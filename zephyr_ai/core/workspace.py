"""
Zephyr/west workspace discovery and normalization.

All higher-level tools should resolve a workspace through this module to ensure:
- consistent auto-detection
- multi-workspace support
- robust derivation of ZEPHYR_BASE / manifest location
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

from zephyr_ai.core.utils import run_command


@dataclass(frozen=True)
class ZephyrWorkspace:
    root: Path
    zephyr_base: Path
    manifest_path: Optional[Path]

    def as_dict(self) -> dict:
        return {
            "root": str(self.root),
            "zephyr_base": str(self.zephyr_base),
            "manifest_path": str(self.manifest_path) if self.manifest_path else None,
        }


def _normalize_start_path(start_path: Optional[str]) -> Path:
    if not start_path:
        return Path.cwd()
    p = Path(start_path).expanduser()
    if p.is_file():
        return p.parent
    return p


def _is_west_topdir(path: Path) -> bool:
    return (path / ".west" / "config").exists()


def _walk_up_for_west_topdir(start_dir: Path) -> Optional[Path]:
    cur = start_dir.resolve()
    for parent in [cur, *cur.parents]:
        if _is_west_topdir(parent):
            return parent
    return None


def _west_topdir_via_cli(start_dir: Path) -> Optional[Path]:
    # `west topdir` prints the topdir path when called from inside a workspace.
    res = run_command(["west", "topdir"], cwd=str(start_dir))
    if res["returncode"] != 0:
        return None
    out = (res["stdout"] or "").strip()
    if not out:
        return None
    p = Path(out).expanduser()
    if _is_west_topdir(p):
        return p.resolve()
    return None


def find_west_topdir(
    *, workspace_root: Optional[str] = None, start_path: Optional[str] = None
) -> Path:
    """
    Resolve a west topdir.

    Priority:
    1) explicit workspace_root
    2) walk-up from start_path (or cwd)
    3) `west topdir` CLI (cwd=start_path)
    """
    if workspace_root:
        p = Path(workspace_root).expanduser().resolve()
        if not _is_west_topdir(p):
            raise ValueError(f"Not a west workspace (missing .west/config): {p}")
        return p

    start_dir = _normalize_start_path(start_path)
    top = _walk_up_for_west_topdir(start_dir)
    if top:
        return top

    top = _west_topdir_via_cli(start_dir)
    if top:
        return top

    raise ValueError(
        f"Could not auto-detect a west workspace from: {start_dir}. "
        "Pass workspace_root explicitly."
    )


def _guess_zephyr_base_from_layout(topdir: Path) -> Optional[Path]:
    # Typical Zephyr workspace layout places zephyr repository at <topdir>/zephyr
    candidate = topdir / "zephyr"
    if (candidate / "VERSION").exists() and (candidate / "CMakeLists.txt").exists():
        return candidate.resolve()
    return None


def _zephyr_base_from_west_list(topdir: Path) -> Optional[Path]:
    # Use west itself to locate project named "zephyr" if available.
    # We avoid importing west as a Python lib and instead shell out for stability.
    res = run_command(
        ["west", "list", "-f", "{name} {path}"], cwd=str(topdir)
    )
    if res["returncode"] != 0:
        return None
    for line in (res["stdout"] or "").splitlines():
        try:
            name, relpath = line.strip().split(" ", 1)
        except ValueError:
            continue
        if name == "zephyr":
            p = (topdir / relpath.strip()).resolve()
            if (p / "VERSION").exists():
                return p
    return None


def _manifest_path_from_west(topdir: Path) -> Optional[Path]:
    # `west manifest --path` prints the manifest file.
    res = run_command(["west", "manifest", "--path"], cwd=str(topdir))
    if res["returncode"] != 0:
        return None
    out = (res["stdout"] or "").strip()
    if not out:
        return None
    p = Path(out).expanduser()
    if not p.is_absolute():
        p = topdir / p
    if p.exists():
        return p.resolve()
    return None


def resolve_workspace(
    *, workspace_root: Optional[str] = None, start_path: Optional[str] = None
) -> ZephyrWorkspace:
    topdir = find_west_topdir(workspace_root=workspace_root, start_path=start_path)

    zephyr_base = None
    env_zephyr_base = os.getenv("ZEPHYR_BASE")
    if env_zephyr_base:
        p = Path(env_zephyr_base).expanduser()
        if not p.is_absolute():
            p = topdir / p
        if (p / "VERSION").exists():
            zephyr_base = p.resolve()

    if zephyr_base is None:
        zephyr_base = _guess_zephyr_base_from_layout(topdir) or _zephyr_base_from_west_list(topdir)

    if zephyr_base is None:
        raise ValueError(
            f"Could not determine ZEPHYR_BASE for workspace: {topdir}. "
            "Ensure the zephyr project is present (e.g. <topdir>/zephyr)."
        )

    manifest_path = _manifest_path_from_west(topdir)
    return ZephyrWorkspace(root=topdir, zephyr_base=zephyr_base, manifest_path=manifest_path)


def parse_workspaces_env(var_name: str = "ZEPHYR_AI_WORKSPACES") -> List[Path]:
    """
    Optional multi-workspace hint.
    Format: colon-separated list of directories, each expected to be a west topdir.
    """
    raw = os.getenv(var_name, "").strip()
    if not raw:
        return []
    paths: List[Path] = []
    for part in raw.split(os.pathsep):
        part = part.strip()
        if not part:
            continue
        p = Path(part).expanduser().resolve()
        if _is_west_topdir(p):
            paths.append(p)
    # unique, stable
    uniq: List[Path] = []
    seen = set()
    for p in paths:
        if str(p) in seen:
            continue
        seen.add(str(p))
        uniq.append(p)
    return uniq


def detect_workspaces(start_paths: Optional[Sequence[str]] = None) -> List[dict]:
    """
    Detect unique west workspaces from provided start paths plus optional env hint.
    """
    candidates: List[Path] = []
    for p in parse_workspaces_env():
        candidates.append(p)

    if start_paths:
        for sp in start_paths:
            start_dir = _normalize_start_path(sp)
            top = _walk_up_for_west_topdir(start_dir) or _west_topdir_via_cli(start_dir)
            if top:
                candidates.append(top)

    uniq: List[Path] = []
    seen = set()
    for p in candidates:
        rp = p.resolve()
        if str(rp) in seen:
            continue
        seen.add(str(rp))
        uniq.append(rp)

    out: List[dict] = []
    for p in uniq:
        try:
            ws = resolve_workspace(workspace_root=str(p))
            out.append(ws.as_dict())
        except ValueError as e:
            out.append({"root": str(p), "error": str(e)})
    return out

