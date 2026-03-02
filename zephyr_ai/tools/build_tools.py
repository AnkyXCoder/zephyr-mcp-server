"""
Build/flash/debug tools for Zephyr via west.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from zephyr_ai.core.runner import make_zephyr_env, run_async
from zephyr_ai.core.workspace import resolve_workspace


def _ok(data: Any) -> dict:
    return {"ok": True, "error": None, "data": data}


def _err(message: str, *, hint: Optional[str] = None, type_: str = "Error") -> dict:
    return {"ok": False, "error": {"type": type_, "message": message, "hint": hint}, "data": None}


def _ensure_inside_workspace(ws_root: Path, build_dir: Path) -> Path:
    ws_root = ws_root.resolve()
    build_dir = build_dir.resolve()
    try:
        build_dir.relative_to(ws_root)
    except ValueError as e:
        raise ValueError(f"build_dir must be inside workspace_root. build_dir={build_dir}, workspace_root={ws_root}") from e
    return build_dir


def _default_build_dir(ws_root: Path, board: str, app_path: Path) -> Path:
    safe_board = board.replace("/", "_")
    safe_app = app_path.name
    return (ws_root / "build" / f"{safe_app}_{safe_board}").resolve()


async def build(
    board: str,
    app_path: str,
    workspace_root: Optional[str] = None,
    pristine: bool = True,
    build_dir: Optional[str] = None,
    extra_cmake_args: Optional[List[str]] = None,
    timeout_s: Optional[float] = 600,
) -> dict:
    try:
        ws = resolve_workspace(workspace_root=workspace_root, start_path=app_path)
        app = Path(app_path).expanduser()
        if not app.is_absolute():
            app = ws.root / app
        app = app.resolve()
        if not app.exists():
            return _err(f"app_path does not exist: {app}", type_="NotFound")

        out_dir = Path(build_dir).expanduser() if build_dir else _default_build_dir(ws.root, board, app)
        if not out_dir.is_absolute():
            out_dir = ws.root / out_dir
        out_dir = _ensure_inside_workspace(ws.root, out_dir)
        out_dir.parent.mkdir(parents=True, exist_ok=True)

        cmd = ["west", "build", "-b", board, "-d", str(out_dir), str(app)]
        if pristine:
            cmd.append("--pristine")
        if extra_cmake_args:
            cmd.append("--")
            cmd.extend(extra_cmake_args)

        env = make_zephyr_env(zephyr_base=str(ws.zephyr_base))
        res = await run_async(cmd, cwd=str(ws.root), env=env, timeout_s=timeout_s)
        return _ok({"workspace": ws.as_dict(), "build_dir": str(out_dir), "result": res.as_dict()})
    except ValueError as e:
        return _err(str(e))


async def flash(
    build_dir: str,
    workspace_root: Optional[str] = None,
    runner: Optional[str] = None,
    extra_args: Optional[List[str]] = None,
    timeout_s: Optional[float] = 300,
) -> dict:
    try:
        ws = resolve_workspace(workspace_root=workspace_root, start_path=build_dir)
        bdir = Path(build_dir).expanduser()
        if not bdir.is_absolute():
            bdir = ws.root / bdir
        bdir = _ensure_inside_workspace(ws.root, bdir)
        cmd = ["west", "flash", "-d", str(bdir)]
        if runner:
            cmd.extend(["-r", runner])
        if extra_args:
            cmd.append("--")
            cmd.extend(extra_args)
        env = make_zephyr_env(zephyr_base=str(ws.zephyr_base))
        res = await run_async(cmd, cwd=str(ws.root), env=env, timeout_s=timeout_s)
        return _ok({"workspace": ws.as_dict(), "build_dir": str(bdir), "result": res.as_dict()})
    except ValueError as e:
        return _err(str(e))


async def build_flash(
    board: str,
    app_path: str,
    workspace_root: Optional[str] = None,
    pristine: bool = True,
    build_dir: Optional[str] = None,
    extra_cmake_args: Optional[List[str]] = None,
    runner: Optional[str] = None,
    flash_extra_args: Optional[List[str]] = None,
) -> dict:
    b = await build(
        board=board,
        app_path=app_path,
        workspace_root=workspace_root,
        pristine=pristine,
        build_dir=build_dir,
        extra_cmake_args=extra_cmake_args,
    )
    if not b.get("ok"):
        return b
    f = await flash(
        build_dir=b["data"]["build_dir"],
        workspace_root=workspace_root,
        runner=runner,
        extra_args=flash_extra_args,
    )
    return _ok({"build": b["data"], "flash": f.get("data"), "flash_ok": bool(f.get("ok"))})


# ---- Debugserver management (long-running) ----

@dataclass
class DebugSession:
    session_id: str
    build_dir: str
    started_at: float
    argv: List[str]
    process: asyncio.subprocess.Process
    log: Deque[str]


_debug_sessions: Dict[str, DebugSession] = {}


async def _drain_stream(stream: asyncio.StreamReader, buf: Deque[str], prefix: str) -> None:
    while True:
        line = await stream.readline()
        if not line:
            return
        txt = line.decode(errors="replace").rstrip("\n")
        buf.append(f"{prefix}{txt}")


async def debugserver_start(
    build_dir: str,
    workspace_root: Optional[str] = None,
    runner: Optional[str] = None,
    extra_args: Optional[List[str]] = None,
) -> dict:
    try:
        ws = resolve_workspace(workspace_root=workspace_root, start_path=build_dir)
        bdir = Path(build_dir).expanduser()
        if not bdir.is_absolute():
            bdir = ws.root / bdir
        bdir = _ensure_inside_workspace(ws.root, bdir)
        argv = ["west", "debugserver", "-d", str(bdir)]
        if runner:
            argv.extend(["-r", runner])
        if extra_args:
            argv.append("--")
            argv.extend(extra_args)

        env = make_zephyr_env(zephyr_base=str(ws.zephyr_base))
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(ws.root),
            env=env,
        )

        session_id = uuid.uuid4().hex
        log: Deque[str] = deque(maxlen=500)
        sess = DebugSession(
            session_id=session_id,
            build_dir=str(bdir),
            started_at=time.time(),
            argv=argv,
            process=proc,
            log=log,
        )
        _debug_sessions[session_id] = sess

        # background drain
        if proc.stdout:
            asyncio.create_task(_drain_stream(proc.stdout, log, "stdout: "))
        if proc.stderr:
            asyncio.create_task(_drain_stream(proc.stderr, log, "stderr: "))

        # Give it a brief moment to produce initial logs.
        await asyncio.sleep(0.5)

        return _ok(
            {
                "workspace": ws.as_dict(),
                "session_id": session_id,
                "argv": argv,
                "pid": proc.pid,
                "build_dir": str(bdir),
                "recent_log": list(log),
            }
        )
    except ValueError as e:
        return _err(str(e))


def debugserver_status(session_id: str) -> dict:
    sess = _debug_sessions.get(session_id)
    if not sess:
        return _err(f"Unknown session_id: {session_id}", type_="NotFound")
    rc = sess.process.returncode
    return _ok(
        {
            "session_id": session_id,
            "pid": sess.process.pid,
            "running": rc is None,
            "returncode": rc,
            "build_dir": sess.build_dir,
            "argv": sess.argv,
            "uptime_s": time.time() - sess.started_at,
            "recent_log": list(sess.log),
        }
    )


async def debugserver_stop(session_id: str) -> dict:
    sess = _debug_sessions.get(session_id)
    if not sess:
        return _err(f"Unknown session_id: {session_id}", type_="NotFound")
    if sess.process.returncode is None:
        sess.process.terminate()
        try:
            await asyncio.wait_for(sess.process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            sess.process.kill()
            await sess.process.wait()
    rc = sess.process.returncode
    _debug_sessions.pop(session_id, None)
    return _ok({"session_id": session_id, "returncode": rc, "recent_log": list(sess.log)})


async def build_flash_debug(
    board: str,
    app_path: str,
    workspace_root: Optional[str] = None,
    pristine: bool = True,
    build_dir: Optional[str] = None,
    extra_cmake_args: Optional[List[str]] = None,
    runner: Optional[str] = None,
    flash_extra_args: Optional[List[str]] = None,
    debugserver_extra_args: Optional[List[str]] = None,
) -> dict:
    bf = await build_flash(
        board=board,
        app_path=app_path,
        workspace_root=workspace_root,
        pristine=pristine,
        build_dir=build_dir,
        extra_cmake_args=extra_cmake_args,
        runner=runner,
        flash_extra_args=flash_extra_args,
    )
    if not bf.get("ok"):
        return bf
    # Even if flash fails, allow user to still start debugserver if build succeeded.
    bdir = bf["data"]["build"]["build_dir"]
    ds = await debugserver_start(
        build_dir=bdir,
        workspace_root=workspace_root,
        runner=runner,
        extra_args=debugserver_extra_args,
    )
    return _ok({"build_flash": bf["data"], "debugserver": ds.get("data"), "debugserver_ok": bool(ds.get("ok"))})

