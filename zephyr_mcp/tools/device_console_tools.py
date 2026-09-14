"""
Device console tools: serial port logs/commands and JLink RTT logging.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, Dict, Optional

import serial


def _ok(data: dict) -> dict:
    return {"ok": True, "error": None, "data": data}


def _err(message: str, *, hint: Optional[str] = None, type_: str = "Error") -> dict:
    return {"ok": False, "error": {"type": type_, "message": message, "hint": hint}, "data": None}


# --- Serial console ---


@dataclass
class SerialSession:
    session_id: str
    port: str
    baudrate: int
    started_at: float
    serial: serial.Serial
    log: Deque[str]
    reader_task: asyncio.Task
    stop_event: asyncio.Event


_serial_sessions: Dict[str, SerialSession] = {}


async def _serial_reader(sess: SerialSession) -> None:
    loop = asyncio.get_running_loop()
    while not sess.stop_event.is_set():
        try:
            line = await asyncio.wait_for(
                loop.run_in_executor(None, sess.serial.readline), timeout=0.5
            )
            if line:
                sess.log.append(line.decode(errors="replace").rstrip("\n"))
        except asyncio.TimeoutError:
            continue
        except Exception as e:  # noqa: BLE001
            sess.log.append(f"[serial error] {e}")
            break


async def serial_log_start(port: str, baudrate: int = 115200) -> dict:
    if not os.path.exists(port):
        return _err(f"Port not found: {port}", type_="NotFound")
    try:
        ser = serial.Serial(port, baudrate, timeout=1.0)
    except Exception as e:  # noqa: BLE001
        return _err(f"Failed to open {port}: {e}")

    session_id = uuid.uuid4().hex
    log: Deque[str] = deque(maxlen=2000)
    stop = asyncio.Event()
    sess = SerialSession(
        session_id=session_id,
        port=port,
        baudrate=baudrate,
        started_at=time.time(),
        serial=ser,
        log=log,
        reader_task=None,  # type: ignore[assignment]
        stop_event=stop,
    )
    task = asyncio.create_task(_serial_reader(sess))
    sess.reader_task = task
    _serial_sessions[session_id] = sess
    return _ok(
        {
            "session_id": session_id,
            "port": port,
            "baudrate": baudrate,
            "recent_log": list(log),
        }
    )


def serial_log_status(session_id: str) -> dict:
    sess = _serial_sessions.get(session_id)
    if not sess:
        return _err(f"Unknown session_id: {session_id}", type_="NotFound")
    running = sess.reader_task and not sess.reader_task.done()
    return _ok(
        {
            "session_id": session_id,
            "port": sess.port,
            "baudrate": sess.baudrate,
            "running": running,
            "uptime_s": time.time() - sess.started_at,
            "recent_log": list(sess.log),
        }
    )


async def serial_send_command(session_id: str, command: str) -> dict:
    sess = _serial_sessions.get(session_id)
    if not sess:
        return _err(f"Unknown session_id: {session_id}", type_="NotFound")
    line = command if command.endswith("\n") else command + "\n"
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(None, sess.serial.write, line.encode())
        await loop.run_in_executor(None, sess.serial.flush)
        return _ok({"session_id": session_id, "command": command})
    except Exception as e:  # noqa: BLE001
        return _err(f"Failed to send command: {e}")


async def serial_log_stop(session_id: str) -> dict:
    sess = _serial_sessions.get(session_id)
    if not sess:
        return _err(f"Unknown session_id: {session_id}", type_="NotFound")
    sess.stop_event.set()
    try:
        await asyncio.wait_for(sess.reader_task, timeout=1.5)
    except asyncio.TimeoutError:
        pass
    if sess.serial.is_open:
        sess.serial.close()
    _serial_sessions.pop(session_id, None)
    return _ok({"session_id": session_id, "recent_log": list(sess.log)})


# --- JLink RTT Logger ---


@dataclass
class RttSession:
    session_id: str
    argv: list
    output_path: str
    started_at: float
    process: asyncio.subprocess.Process
    log: Deque[str]


_rtt_sessions: Dict[str, RttSession] = {}


async def _rtt_reader(stream: asyncio.StreamReader, buf: Deque[str], prefix: str) -> None:
    while True:
        line = await stream.readline()
        if not line:
            return
        text = line.decode(errors="replace").rstrip("\n")
        buf.append(f"{prefix}{text}")


def _output_info(path: str) -> dict:
    try:
        if os.path.exists(path):
            return {"exists": True, "size_bytes": os.path.getsize(path)}
        return {"exists": False, "size_bytes": None}
    except OSError:
        return {"exists": False, "size_bytes": None}


async def rtt_log_start(
    device: str = "NRF54L15_M33",
    interface: str = "SWD",
    speed: int = 4000,
    channel: int = 0,
    output_path: str = "/tmp/rtt.log",
) -> dict:
    out = Path(output_path).expanduser()
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return _err(f"Cannot create output directory {out.parent}: {e}")

    argv = [
        "JLinkRTTLogger",
        "-Device",
        device,
        "-If",
        interface,
        "-Speed",
        str(speed),
        "-RTTChannel",
        str(channel),
        str(out),
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except Exception as e:  # noqa: BLE001
        return _err(f"Failed to start JLinkRTTLogger: {e}")

    session_id = uuid.uuid4().hex
    log: Deque[str] = deque(maxlen=500)
    sess = RttSession(
        session_id=session_id,
        argv=argv,
        output_path=str(out),
        started_at=time.time(),
        process=proc,
        log=log,
    )
    _rtt_sessions[session_id] = sess

    if proc.stdout:
        asyncio.create_task(_rtt_reader(proc.stdout, log, "stdout: "))
    if proc.stderr:
        asyncio.create_task(_rtt_reader(proc.stderr, log, "stderr: "))

    await asyncio.sleep(0.5)
    return _ok(
        {
            "session_id": session_id,
            "argv": argv,
            "pid": proc.pid,
            "output_path": str(out),
            "output": _output_info(str(out)),
            "recent_log": list(log),
        }
    )


def rtt_log_status(session_id: str) -> dict:
    sess = _rtt_sessions.get(session_id)
    if not sess:
        return _err(f"Unknown session_id: {session_id}", type_="NotFound")
    rc = sess.process.returncode
    return _ok(
        {
            "session_id": session_id,
            "pid": sess.process.pid,
            "running": rc is None,
            "returncode": rc,
            "argv": sess.argv,
            "output_path": sess.output_path,
            "output": _output_info(sess.output_path),
            "uptime_s": time.time() - sess.started_at,
            "recent_log": list(sess.log),
        }
    )


async def rtt_log_stop(session_id: str) -> dict:
    sess = _rtt_sessions.get(session_id)
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
    _rtt_sessions.pop(session_id, None)
    return _ok(
        {
            "session_id": session_id,
            "returncode": rc,
            "output_path": sess.output_path,
            "output": _output_info(sess.output_path),
            "recent_log": list(sess.log),
        }
    )
