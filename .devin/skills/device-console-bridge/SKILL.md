---
name: device-console-bridge
description: Use when the user wants to capture or interact with a device console -- "open the serial port", "log the UART output", "capture RTT logs", "send a shell command to the board", "what is the board printing", "stop the serial capture". Manages long-running serial (pyserial) and SEGGER RTT (JLinkRTTLogger) capture sessions as background shells, tails their output, injects commands into the device shell, and shuts them down cleanly.
---

# device-console-bridge

Captures device console output over a USB-serial port or a SEGGER RTT channel, keeps it running in the background while other work continues, lets the user send commands to the Zephyr shell, and tears the session down cleanly. Session state lives in a background shell id rather than an MCP `session_id`.

Replaces these `zephyr_ai` MCP tools: `serial_log_start`, `serial_log_status`, `serial_log_stop`, `serial_send_command`, `rtt_log_start`, `rtt_log_status`, `rtt_log_stop`.

## When to use

- User wants to see what a flashed board is printing on its console.
- User wants a UART/RTT log captured to a file while other work proceeds.
- User wants to drive the Zephyr shell (`kernel version`, `device list`, custom commands) and read the reply.
- User wants a boot banner or a specific log line confirmed after a flash.

## When NOT to use

- The board has not been flashed yet (use `west-build-flash` first).
- The user wants simulated console output rather than hardware (use `renode-runner`, which does its own UART capture and assertion).
- The user wants a one-shot assertion on a log file that already exists -- just `grep` it; a session is unnecessary.
- The user wants to diagnose a build failure (use `build-doctor`).

## Required inputs

| Input | Type | Default |
|-------|------|---------|
| `action` | one of: `serial-start`, `serial-status`, `serial-send`, `serial-stop`, `rtt-start`, `rtt-status`, `rtt-stop` | (none -- ask, or infer from phrasing) |
| `port` | serial device path, e.g. `/dev/ttyACM0`, `/dev/ttyUSB0` | auto-detect if exactly one candidate exists (see below) |
| `baudrate` | integer | `115200` |
| `log_path` | file the session writes to | `/tmp/console-<port_basename>.log` (serial), `/tmp/rtt.log` (RTT) |
| `session_shell_id` | background shell id returned by a `*-start` action | (required for `status` / `send` / `stop`) |
| `command` | text to send to the device shell | (required for `serial-send`) |
| `rtt_device` | J-Link device name, e.g. `NRF54L15_M33`, `NRF52840_XXAA` | (required for `rtt-start` -- ask) |
| `rtt_interface` | `SWD` or `JTAG` | `SWD` |
| `rtt_speed` | kHz | `4000` |
| `rtt_channel` | RTT channel index | `0` |
| `tail_lines` | how many recent lines to show on status | `40` |

## Port and tool resolution

**Serial port**: if `port` is not given, list candidates with `ls /dev/ttyACM* /dev/ttyUSB*`. If exactly one exists, use it and say so. If several exist, list them and ask -- never pick arbitrarily, since the wrong port may belong to another engineer's board or a modem.

**Serial reader**: try in order --
1. `python3 -c "import serial"` succeeds → use a pyserial one-liner reader.
2. `which picocom` → `picocom -b <baudrate> <port>`.
3. `which screen` → `screen <port> <baudrate>`.
4. Plain `cat <port>` with `stty` configuring the line (read-only capture; no command injection possible).
Report which one was chosen.

**RTT**: `JLinkRTTLogger` must be on PATH. If `which JLinkRTTLogger` fails, halt and tell the user to install the SEGGER J-Link tools -- do not substitute another tool silently.

## Procedure

1. **Resolve inputs.** For `*-start`: verify the target exists before opening it -- `test -e <port>` for serial (halt with "port not found" if absent), `which JLinkRTTLogger` for RTT. Verify the user has access: if `test -r <port>` fails, report the permission problem (typically the `dialout` group) rather than producing an empty log.
2. **serial-start**: launch a **background** shell (`exec` with `timeout: 0`) running the reader with output tee'd to `log_path`, e.g.
   `python3 -u -m serial.tools.miniterm --raw <port> <baudrate> | tee <log_path>`
   or the pyserial/picocom equivalent chosen above. Report the returned `shell_id` as the session handle. Wait ~1s and capture the first output so the report shows real data.
3. **rtt-start**: launch a **background** shell running
   `JLinkRTTLogger -Device <rtt_device> -If <rtt_interface> -Speed <rtt_speed> -RTTChannel <rtt_channel> <log_path>`
   Report the `shell_id`, the argv used, and whether `log_path` was created.
4. **status**: call `get_output` on `session_shell_id` for the newest lines, and stat `log_path` for its size. Determine "running" from whether the shell still has a live process. Report the byte size so growth is observable across two status calls.
5. **serial-send**: write `<command>\n` to the running session's stdin (`write_to_process` on `session_shell_id`). This requires an interactive-capable reader (miniterm/picocom/screen); if the session was started with plain `cat`, refuse and explain that the session is read-only. After sending, wait briefly and report the newly captured output so the reply is visible.
6. **stop**: terminate the background shell (`kill_shell` on `session_shell_id`), then stat `log_path` one final time. Report the final size and the last `tail_lines` lines. Never delete the log on stop.
7. **Report** with the output format below.

## Self-Validation Protocol

Every check binary; report every check relevant to the action.

| # | Check | How to verify |
|---|-------|---------------|
| 1 | Target exists before opening | `test -e <port>` (serial) or `which JLinkRTTLogger` (RTT) |
| 2 | Session handle is real | a `shell_id` was returned by the background `exec` call |
| 3 | Data is actually flowing | `log_path` exists and its size is > 0, or at least one output line was captured; a zero-byte log after 2s is reported as "no data -- check baudrate/reset the board", not as success |
| 4 | Growth observed between status calls | second `stat` size >= first; if equal, report "no new output since last check" rather than implying activity |
| 5 | Sent command was delivered | the write to stdin returned without error AND the session was started with an interactive reader |
| 6 | Log preserved on stop | `test -s <log_path>` after the session ends |

If check 1 fails: halt. If check 3 fails: report the session as started-but-silent and suggest baudrate/reset -- do not claim capture is working.

## Retry policy

- `serial-start`: at most 1 retry if the port is busy (`Device or resource busy`), after telling the user which process holds it (`fuser <port>` / `lsof <port>` if available).
- `rtt-start`: at most 1 retry if the J-Link probe reports "cannot connect", after suggesting a target reset. Never retry on a wrong-device-name error -- that needs the user.
- `serial-send`: no retry. Re-sending a command to an embedded shell can have side effects.

## Output format

```
device-console-bridge result: PASS  (or FAIL)

Action:   serial-start
Port:     /dev/ttyACM0 @ 115200        (reader: python3 -m serial.tools.miniterm)
Session:  shell_id = 7c2ab9            <- use this for status / send / stop
Log:      /tmp/console-ttyACM0.log  (1.2 KB and growing)

Recent output (last 40 lines):
  *** Booting Zephyr OS build v4.3.0-rc1 ***
  [00:00:00.001,000] <inf> main: application started
  uart:~$

Validation:
  [x] port exists:        /dev/ttyACM0
  [x] session handle:     shell_id 7c2ab9
  [x] data flowing:       1218 bytes captured
  [x] reader interactive: yes (send supported)
```

Stop case:

```
device-console-bridge result: PASS

Action:   serial-stop  (session 7c2ab9)
Log:      /tmp/console-ttyACM0.log  (18.4 KB, preserved)
Last lines:
  uart:~$ kernel version
  Zephyr version 4.3.0

Validation:
  [x] session terminated
  [x] log preserved: 18841 bytes
```

## Examples

### Example 1: capture the boot banner after a flash

User: "flash finished -- what is the board printing?"

Agent finds exactly one `/dev/ttyACM0`, starts a background miniterm session tee'd to `/tmp/console-ttyACM0.log`, waits a second, and reports the captured `*** Booting Zephyr OS ***` banner with the session's `shell_id` so the user can stop it later.

### Example 2: drive the Zephyr shell

User: "send `kernel version` to the board"

Agent writes `kernel version\n` to the running session's stdin, waits, and reports the newly captured reply lines. If the session had been started with plain `cat` (read-only fallback), it refuses and offers to restart the session with an interactive reader.

### Example 3: RTT on a Nordic target

User: "capture RTT logs from the nRF54L15"

Agent verifies `JLinkRTTLogger` is on PATH, starts it in the background with `-Device NRF54L15_M33 -If SWD -Speed 4000 -RTTChannel 0 /tmp/rtt.log`, and reports the session id plus whether `/tmp/rtt.log` started growing. If the log is still zero bytes after two seconds, it reports "started but silent" rather than success.

### Example 4: refusal

User: "just tail the log file from yesterday's run"

Agent refuses to open a session: no device interaction is needed, so it simply reads/greps the existing file. Sessions are for live devices.

## Elevator pitch (for slides)

device-console-bridge is the MCP serial/RTT session tool group without the MCP server: a background shell id replaces `session_id`, `get_output` replaces `*_log_status`, stdin injection replaces `serial_send_command`, and killing the shell replaces `*_log_stop`. Six binary checks mean a silent port is reported as silent instead of being dressed up as a working capture.
