---
name: west-build-flash
description: Use when the user asks to build, flash, or start a debug server for a Zephyr application. Triggers include "build hello_world for nrf52840dk", "west build this app", "flash the board", "build and flash", "start a debugserver", "what's in my build directory". Runs `west build` / `west flash` / `west debugserver` with an explicit build directory, verifies the produced artifacts exist, and manages the debugserver as a background shell session. Hands failed builds to build-doctor.
---

# west-build-flash

Runs the Zephyr build/flash/debug lifecycle through `west` with an explicit, workspace-local build directory, then proves the result by checking the artifacts that must exist on disk. Long-running `west debugserver` runs as a background shell whose id plays the role an MCP `session_id` would.

Replaces these `zephyr_ai` MCP tools: `build`, `flash`, `build_flash`, `build_flash_debug`, `debugserver_start`, `debugserver_status`, `debugserver_stop`, `get_build_info`.

## When to use

- User wants an application built for a board target, with or without flashing afterwards.
- User wants an existing build directory flashed to hardware, optionally with a specific runner.
- User wants a GDB server started against a build directory and later stopped.
- User asks what a build directory contains (artifacts, `.config`, runners).

## When NOT to use

- The build failed and the user wants to know *why* (use `build-doctor` -- this skill hands off to it, it does not classify errors itself).
- The user wants to run in simulation instead of on hardware (use `renode-runner`).
- The user wants to change CONFIG symbols (use `kconfig-tuner`) or devicetree (use `devicetree-author`) before building.
- The user wants a test-suite run rather than a single app build (use `twister-runner`).
- The user wants serial or RTT console output after flashing (use `device-console-bridge`).

## Required inputs

| Input | Type | Default |
|-------|------|---------|
| `action` | one of: `build`, `flash`, `build-flash`, `debugserver-start`, `debugserver-status`, `debugserver-stop`, `build-info` | (none -- ask, or infer from the user's phrasing) |
| `board` | Zephyr board target, e.g. `nrf52840dk/nrf52840`, `esp32s3_devkitc/esp32s3/procpu` | (required for build actions -- ask) |
| `app_path` | path to the application directory (contains `CMakeLists.txt`) | current directory if it contains `CMakeLists.txt` |
| `build_dir` | build output directory, **must be inside the workspace root** | `<workspace_root>/build/<app_name>_<board_with_slashes_as_underscores>` |
| `pristine` | pass `--pristine` to force a clean build | `true` for `build`, `false` when re-flashing an existing dir |
| `runner` | `west flash -r <runner>` value (`jlink`, `openocd`, `pyocd`, `linkserver`, `esp32`, ...) | none (west picks the board default) |
| `extra_cmake_args` | args appended after `--` on `west build` | none |
| `flash_extra_args` | args appended after `--` on `west flash` | none |
| `session_shell_id` | the background shell id of a running debugserver | (required for `debugserver-status` / `debugserver-stop`) |
| `workspace_root` | west workspace root | auto-detect (see below) |
| `timeout_s` | build timeout in seconds | `600` for build, `300` for flash |

## Workspace resolution

Try in order, take the first that resolves (same chain as `west-workspace-inspector`):

1. `ZEPHYR_BASE` env var → `workspace_root = $(dirname $ZEPHYR_BASE)` when it contains `.west/`.
2. `west topdir`.
3. Walk up from `app_path` looking for `.west/`.
4. `/workdir` or `./zephyrproject`.
5. Ask the user.

`build_dir` MUST resolve to a path inside `workspace_root`. If the user supplies one outside it, halt and say so -- do not silently relocate it.

## Procedure

1. **Resolve** `workspace_root`, `app_path`, and `build_dir`. Verify `test -d <app_path>` and `test -f <app_path>/CMakeLists.txt`; halt if either fails. Verify `build_dir` is inside `workspace_root`; halt if not. Create the parent of `build_dir` if needed.
2. **Build** (`build`, `build-flash`): run
   `west build -b <board> -d <build_dir> <app_path> [--pristine] [-- <extra_cmake_args>]`
   from `workspace_root`, capturing stdout and stderr to a file (e.g. `/tmp/west-build-<name>.log`). Record the exit code.
   - **On non-zero exit: stop the lifecycle here.** Report the failure and invoke `build-doctor` with the captured stderr path. Do not attempt to flash, and do not attempt your own error classification.
3. **Verify build artifacts** (see Self-Validation checks 2-3) before claiming success. A zero exit code with no `zephyr.elf` is a failure, not a success.
4. **Flash** (`flash`, `build-flash`): run
   `west flash -d <build_dir> [-r <runner>] [-- <flash_extra_args>]`
   from `workspace_root`. Record the exit code and the last 20 lines of output. Flash failures are usually probe/permissions issues -- report the runner's own message verbatim rather than paraphrasing.
5. **Debugserver start**: launch `west debugserver -d <build_dir> [-r <runner>]` as a **background** shell (`exec` with `timeout: 0`). Report the returned `shell_id` -- this is the session handle, the direct analogue of the MCP `session_id`. Poll once with `get_output` after a short delay so the report includes the server's initial banner (the port it is listening on).
6. **Debugserver status**: call `get_output` on `session_shell_id` and report whether the process is still running plus the newest output lines.
7. **Debugserver stop**: terminate the background shell for `session_shell_id` (`kill_shell`), then confirm it is gone. Report the final output tail.
8. **Build info** (`build-info`): stat these paths under `<build_dir>` and report size + mtime for each that exists: `CMakeCache.txt`, `zephyr/.config`, `zephyr/runners.yaml`, `zephyr/zephyr.elf`, `zephyr/zephyr.hex`, `zephyr/zephyr.bin`, `zephyr/zephyr.dts`, `zephyr/edt.pickle`. Optionally print the first 40 lines of `zephyr/.config`.

## Self-Validation Protocol

Every check binary; report every check relevant to the action taken.

| # | Check | How to verify |
|---|-------|---------------|
| 1 | `build_dir` is inside `workspace_root` | path prefix comparison after resolving both to absolute paths |
| 2 | Build exit code captured | record the literal integer; never report "built" without it |
| 3 | Build artifacts exist | `test -f <build_dir>/zephyr/zephyr.elf` and `test -f <build_dir>/zephyr/.config` |
| 4 | Flash exit code captured and zero | `west flash` exit code == 0; non-zero is reported with the runner's message |
| 5 | Debugserver session handle is real | `shell_id` returned by the background `exec` call, plus at least one captured output line |
| 6 | Build-info paths were stat-ed, not assumed | every file listed as present passed `test -f` |

If check 3 fails after a zero exit code: report **failure**, not success, and state which artifact is missing. If check 1 fails: halt before running anything.

## Retry policy

- Build: no automatic retry. A failed build goes to `build-doctor`; retrying a broken build wastes minutes and changes nothing.
- Flash: at most 1 retry, and only when the error text clearly indicates a transient probe issue (`Unable to connect to target`, `LIBUSB_ERROR_BUSY`, `device busy`). Never retry a flash that failed on a verification mismatch.
- Debugserver start: at most 1 retry if the failure is "address already in use", after reporting the conflicting port to the user.

## Output format

```
west-build-flash result: PASS  (or FAIL)

Action:      build-flash
Board:       nrf52840dk/nrf52840
App:         /home/user/zephyrproject/zephyr/samples/hello_world
Build dir:   /home/user/zephyrproject/build/hello_world_nrf52840dk_nrf52840
Command:     west build -b nrf52840dk/nrf52840 -d <build_dir> <app> --pristine   (exit 0, 48.2s)
Flash:       west flash -d <build_dir> -r jlink                                  (exit 0)

Artifacts:
  zephyr.elf   612 KB   2026-08-22 10:14
  zephyr.hex   198 KB   2026-08-22 10:14
  .config       41 KB   2026-08-22 10:13

Validation:
  [x] build_dir inside workspace:  yes
  [x] build exit code:             0
  [x] artifacts present:           zephyr.elf, .config
  [x] flash exit code:             0
  [ ] debugserver session:         n/a (not requested)
```

Failure case:

```
west-build-flash result: FAIL

Action:  build
Command: west build -b nrf52840dk/nrf52840 -d <build_dir> <app> --pristine   (exit 1, 12.4s)
stderr:  /tmp/west-build-hello_world.log (1842 bytes)

Handing off to build-doctor for classification. Not flashing.
```

## Examples

### Example 1: build and flash

User: "build hello_world for nrf52840dk and flash it"

Agent resolves the workspace, builds into `<workspace>/build/hello_world_nrf52840dk_nrf52840` with `--pristine`, confirms `zephyr.elf` and `.config` exist, then runs `west flash -d <build_dir>`. Reports both exit codes and the artifact table.

### Example 2: build fails

User: "build my app for frdm_mcxa156"

`west build` exits 1. The agent reports the failure with the captured stderr path, does **not** flash, and invokes `build-doctor` with that stderr so the error is classified there. It never guesses at the cause itself.

### Example 3: debugserver lifecycle

User: "start a gdb server for my build"

Agent launches `west debugserver -d <build_dir>` as a background shell, reports `session (shell_id): a3f19c` plus the captured "Listening on port 2331" line. Later, "stop the debug server" terminates that shell and reports the final output tail.

## Elevator pitch (for slides)

west-build-flash is the MCP build/flash/debug tool group rebuilt as a Devin CLI skill: same `west` invocations, same explicit `-d <build_dir>` discipline, same workspace containment rule -- but the debugserver `session_id` is a background shell id, and a zero exit code is never trusted on its own, because the skill checks that `zephyr.elf` actually landed on disk.
