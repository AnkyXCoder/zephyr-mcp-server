# MCP-to-CLI Guide: replacing an MCP server with Devin CLI skills

How to get everything the `zephyr_ai` MCP server did — and everything a typical vendor-CLI MCP server does — without running an MCP server at all. Written for the case where MCP is disabled by enterprise policy, but equally useful when you simply do not want a long-lived server process between the agent and your toolchain.

The same recipe works with other agent CLIs that support a markdown "skill"/"command"/"rule" file convention (Claude Code, Cursor, Windsurf), because nothing here depends on Devin-specific machinery beyond "run a shell command" and "read a file".

---

## 1. Why this works

The `zephyr_ai` server (`~/zephyr_mcp/zephyr_ai/core/server.py`) registers 28 tools on a `FastMCP` instance. Reading every tool module, all 28 reduce to exactly two primitives:

**Shell-out wrappers.** The tool builds an argv, runs it as a subprocess, and returns stdout/stderr/returncode:

| Module                          | Command it actually runs                                                                                              |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `tools/build_tools.py`          | `west build -b <board> -d <dir> <app> [--pristine]`, `west flash -d <dir> [-r <runner>]`, `west debugserver -d <dir>` |
| `tools/workspace_tools.py`      | `west manifest --resolve`                                                                                             |
| `tools/twister_tools.py`        | `west twister -T <root> -p <platform> -o <reportdir>`                                                                 |
| `analysis/cppcheck.py`          | `cppcheck --enable=all <path>`                                                                                        |
| `tools/device_console_tools.py` | pyserial `Serial(port, baud)` reads/writes; `JLinkRTTLogger -Device … -If … -Speed … -RTTChannel … <log>`             |

**Local file parsers.** The tool reads files off disk and reshapes them:

| Module                      | What it reads                                                                                   |
| --------------------------- | ----------------------------------------------------------------------------------------------- |
| `tools/kconfig_tools.py`    | walks `ZEPHYR_BASE`, greps files named `Kconfig*` for a symbol                                  |
| `tools/boards_tools.py`     | globs `boards/*/*/board.yml` and `boards/shields/*/*/shield.yml`, reads YAML                    |
| `tools/devicetree_tools.py` | reads `<build>/zephyr/zephyr.dts` (lines containing `status = "okay"`), optionally `edt.pickle` |
| `tools/build_info_tools.py` | `stat`s `CMakeCache.txt`, `.config`, `zephyr.elf/hex/bin/dts`, `runners.yaml`                   |
| `firmware/mcuboot.py`       | reads 32 header bytes, `struct.unpack` of the magic                                             |

Now look at what an MCP tool definition actually is:

1. a typed function signature (JSON schema) so the model knows how to call it,
2. a fixed recipe — the argv template and the parsing/validation logic,
3. a JSON-shaped return so the model can reason about the result.

An agent CLI already has (1) and (3) generically: `exec` takes a command string and returns stdout/stderr/exit code; `read` and `grep` return file contents and matches. What MCP was really contributing was **(2): the codified recipe** — "for this task, run *exactly* this command with *exactly* these flags, then check *exactly* these things before you believe the result."

That is precisely what a **skill** (`SKILL.md`) is. So the migration is not a workaround; it is removing a transport layer that was carrying documentation.

**What you lose:** nothing in capability. The subprocess is still a subprocess; the file is still a file. What changes is that the recipe is enforced by a written procedure the agent follows and self-validates against, rather than by Python code the agent calls blindly.

**What you gain:**
- No server process, no venv drift, no `mcp_config.json`, no restart-to-pick-up-changes. Edit the markdown, next session has it.
- The recipe is readable and reviewable by your team in a PR, not buried in a wrapper function.
- Self-validation is explicit and auditable ("this claim is backed by `test -f`"), which is the part that actually makes agent output trustworthy.
- Composability: skills can defer to each other (`west-build-flash` → `build-doctor`) in a way MCP tools generally do not.

**Where the mapping is approximate:** stateful session tools. See section 4.

---

## 2. The generic recipe

Five steps to convert any CLI-wrapping MCP tool into a skill. Vendor-agnostic — nothing below is Zephyr-specific.

### Step 1 — Extract the command template

Open the MCP tool's source and find the argv it builds. Write it down as a template with named holes, and note which flags are required vs optional:

```
west build -b <board> -d <build_dir> <app_path> [--pristine] [-- <extra_cmake_args>]
```

Do this from the source, not from memory or vendor docs — the whole value of the MCP tool was that somebody already got the flags right. If the tool sets environment variables (`ZEPHYR_BASE`, `PATH` additions from a venv), capture those too; they are part of the template.

### Step 2 — Extract the parsing and validation logic

What did the tool do with the output? Typically one of:

- **Exit code only** → the skill records the literal exit code.
- **Structured artifact** → e.g. Twister's `twister.json`, cppcheck's XML. Always prefer the machine-readable artifact over scraping console text, and make its existence a validation check.
- **Regex/string match** → e.g. "Hash of data verified", a MAC address. Write the literal pattern into the skill.
- **File existence** → e.g. `zephyr.elf` after a build. This is the most valuable check to codify, because tools lie: cppcheck exits 0 with findings, Twister exits 0 when it selected zero tests, and CMake can exit 0 without producing an ELF.

Anything the original tool checked defensively (path containment, "does the port exist", "is the file big enough for a header") becomes a validation row.

### Step 3 — Classify statefulness

- **One-shot** (build, flash, lint, parse a file) → an ordinary skill. Run, check, report.
- **Session-based** (a debug server, a serial monitor, a log tail) → the tool had a `start`/`status`/`stop` triple keyed by a `session_id`. In a CLI agent, run the process as a **background shell** and use the shell id as the session handle. See section 4.

### Step 4 — Write the `SKILL.md`

Use the seven-part template that the existing skills in this repo follow:

```
---
name: <kebab-case-name>
description: <what it does + the literal trigger phrases users say>
---

## When to use            <- routing in
## When NOT to use        <- routing out, naming the sibling skill by name
## Required inputs        <- table: input | type | default
## <Resolution chain>     <- how to auto-discover defaults, in strict order
## Procedure              <- numbered steps, each with a halt condition
## Self-Validation Protocol  <- table of binary checks with literal verify commands
## Retry policy           <- when to retry, and explicitly when NOT to
## Output format          <- fixed block including the validation table
## Examples               <- >=1 success, >=1 refusal
```

Two sections do the heavy lifting and are the ones people skip:

- **When NOT to use** — without it, overlapping skills fight for the same request. Name the sibling explicitly: "the build failed and you want to know why → `build-doctor`".
- **Self-Validation Protocol** — every check must be *binary* and *literally verifiable*: `test -f`, `grep -q`, an exit code, an arithmetic identity. "Looks correct" is not a check.

`embedded-skill-author` (in this repo) generates this scaffold interactively and adds a multi-run determinism harness; use it rather than writing from scratch.

### Step 5 — Make every claim falsifiable

The rule that makes this trustworthy: **the skill may not state anything it cannot back with a command that ran.** Concretely:

- Don't report a build as successful on exit code alone — check the artifact exists.
- Don't report a file path you haven't `test -f`'d.
- Don't report a count you can't reconcile (printed + truncated == total).
- Don't paper over a failed subcommand — report its stderr verbatim.
- Prefer an honest "inconclusive" to a confident guess.

---

## 3. Tool-by-tool mapping: `zephyr_ai` → Devin CLI skills

All 28 registered tools, accounted for:

| #   | MCP tool                 | Underlying operation                 | Replacement                                           |
| --- | ------------------------ | ------------------------------------ | ----------------------------------------------------- |
| 1   | `debug_env`              | read `sys.executable`, `ZEPHYR_BASE` | none needed — `exec: env \| grep ZEPHYR_BASE`         |
| 2   | `detect_west_workspaces` | find `.west/` dirs                   | **`west-workspace-inspector`**                        |
| 3   | `analyze_workspace`      | resolve root/zephyr_base             | **`west-workspace-inspector`**                        |
| 4   | `analyze_west_workspace` | resolve + manifest project count     | **`west-workspace-inspector`**                        |
| 5   | `get_zephyr_version`     | read `<zephyr>/VERSION`              | **`west-workspace-inspector`**                        |
| 6   | `parse_west_manifest`    | `west manifest --resolve` + YAML     | **`west-workspace-inspector`**                        |
| 7   | `list_modules`           | manifest `projects[]`                | **`west-workspace-inspector`**                        |
| 8   | `list_boards`            | glob `board.yml` / `shield.yml`      | **`west-workspace-inspector`**                        |
| 9   | `build`                  | `west build -b … -d … [--pristine]`  | **`west-build-flash`**                                |
| 10  | `flash`                  | `west flash -d … [-r …]`             | **`west-build-flash`**                                |
| 11  | `build_flash`            | build then flash                     | **`west-build-flash`**                                |
| 12  | `debugserver_start`      | bg `west debugserver -d …`           | **`west-build-flash`** (background shell)             |
| 13  | `debugserver_status`     | poll session log                     | **`west-build-flash`** (`get_output`)                 |
| 14  | `debugserver_stop`       | terminate session                    | **`west-build-flash`** (kill shell)                   |
| 15  | `build_flash_debug`      | the three chained                    | **`west-build-flash`**                                |
| 16  | `get_build_info`         | stat build artifacts                 | **`west-build-flash`** (`build-info` action)          |
| 17  | `serial_log_start`       | pyserial reader thread               | **`device-console-bridge`**                           |
| 18  | `serial_log_status`      | read session buffer                  | **`device-console-bridge`**                           |
| 19  | `serial_send_command`    | write to serial                      | **`device-console-bridge`** (stdin write)             |
| 20  | `serial_log_stop`        | close port                           | **`device-console-bridge`**                           |
| 21  | `rtt_log_start`          | bg `JLinkRTTLogger …`                | **`device-console-bridge`**                           |
| 22  | `rtt_log_status`         | poll process + log size              | **`device-console-bridge`**                           |
| 23  | `rtt_log_stop`           | terminate process                    | **`device-console-bridge`**                           |
| 24  | `search_kconfig_symbol`  | grep `Kconfig*`                      | existing **`kconfig-tuner`** (its search/verify step) |
| 25  | `parse_devicetree`       | read `zephyr.dts` / `edt.pickle`     | **`devicetree-inspector`**                            |
| 26  | `run_twister`            | `west twister … -o <dir>` + JSON     | **`twister-runner`**                                  |
| 27  | `run_cppcheck`           | `cppcheck --enable=all <path>`       | **`static-analysis-runner`**                          |
| 28  | `analyze_image`          | MCUboot header unpack                | **`mcuboot-image-inspector`**                         |

(Verify the count yourself: `grep -c 'mcp\.tool()' zephyr_ai/core/server.py` → 28.)

### The resulting skill set in `skills/`

Pre-existing (unchanged by this migration):

| Skill                   | Role                                                                            |
| ----------------------- | ------------------------------------------------------------------------------- |
| `kconfig-tuner`         | English goal → verified minimal `CONFIG_*` diff; subsumes Kconfig symbol search |
| `devicetree-author`     | Author/modify `.dts` / `.overlay` with binding citations                        |
| `zephyr-bsp-scaffold`   | Mirror a reference BSP into a new board                                         |
| `build-doctor`          | Classify a failed `west build` into one of five categories                      |
| `renode-runner`         | Run an ELF in Renode, assert on UART output                                     |
| `embedded-skill-author` | Meta-skill: author new skills + determinism harness                             |

Added by this migration:

| Skill                      | Replaces    |
| -------------------------- | ----------- |
| `west-workspace-inspector` | tools 2–8   |
| `west-build-flash`         | tools 9–16  |
| `device-console-bridge`    | tools 17–23 |
| `devicetree-inspector`     | tool 25     |
| `twister-runner`           | tool 26     |
| `static-analysis-runner`   | tool 27     |
| `mcuboot-image-inspector`  | tool 28     |

Routing between them is enforced by each skill's **When NOT to use** section, e.g. `west-build-flash` explicitly refuses to classify build errors and hands the captured stderr to `build-doctor`; `devicetree-inspector` refuses to edit and hands off to `devicetree-author`.

---

## 4. Session and stateful tools without MCP

This is the only place where the mapping is approximate rather than exact, so it deserves its own treatment.

**The MCP pattern.** A long-running tool is split into three calls sharing an opaque handle:

```
rtt_log_start(device=…, channel=0, output_path=…) -> { session_id: "a1b2…", pid, recent_log }
rtt_log_status(session_id)                        -> { running, uptime_s, recent_log }
rtt_log_stop(session_id)                          -> { returncode, output }
```

Server-side, `zephyr_ai` keeps a module-level dict (`_rtt_sessions`, `_serial_sessions`, `_debug_sessions`) of dataclasses holding the subprocess handle and a `deque` ring buffer drained by a background task.

**The CLI equivalent.** The agent's shell tooling already provides all three pieces:

| MCP concept                       | CLI equivalent                                                                          |
| --------------------------------- | --------------------------------------------------------------------------------------- |
| `session_id`                      | the background shell id returned by `exec`                                              |
| background drain into a `deque`   | the shell's own captured output buffer + `tee` to a log file                            |
| `*_status(session_id)`            | `get_output(shell_id, incremental=true)` — returns only what's new since your last read |
| `*_send_command(session_id, cmd)` | write to the running shell's stdin                                                      |
| `*_stop(session_id)`              | kill the background shell                                                               |
| `recent_log` ring buffer          | `tail -n <N> <log_path>`                                                                |

**Worked snippet — serial capture as a background shell:**

```bash
# start: background it explicitly (timeout: 0), tee so the log survives the session
python3 -u -m serial.tools.miniterm --raw /dev/ttyACM0 115200 | tee /tmp/console-ttyACM0.log
# -> returns shell_id "7c2ab9"   <- this is your session_id

# status: incremental read of what's new, plus observable growth
stat -c %s /tmp/console-ttyACM0.log

# send: write "kernel version\n" to that shell's stdin

# stop: kill shell 7c2ab9; the log file remains at /tmp/console-ttyACM0.log
```

**The three real differences, stated honestly:**

1. **The handle is not typed.** MCP returned a JSON object with `session_id`, `pid`, `running`, `uptime_s`. A shell id is just a string; the skill has to report the surrounding metadata itself. `device-console-bridge` compensates by always printing the log path and its byte size, so "is it alive and receiving?" is answerable by comparing two status calls.
2. **Stdin injection depends on the reader.** A session started as `cat /dev/ttyACM0` is read-only; you cannot send shell commands into it. The skill therefore records *which* reader it chose (miniterm/picocom/screen/cat) and refuses `serial-send` on a read-only session instead of silently doing nothing.
3. **Sessions do not outlive the agent session.** MCP servers can hold a process across conversations; a background shell belongs to the current CLI session. For captures that must outlive it, write to a log file (which the skill always does) or use `nohup`/`systemd-run` and treat the log file as the handle.

For everything else — build servers, debug servers, monitors, log tails — the background-shell model is a drop-in replacement.

---

## 5. Applying the recipe to another vendor's CLI

The recipe is vendor-agnostic because step 1 only asks "what argv does this tool run?". Here it is end-to-end on a toolchain that has nothing to do with `west`.

### Worked example: Espressif (`esptool.py` / `idf.py`)

**Step 1 — command templates.** From the vendor docs / the MCP wrapper you're replacing:

```
esptool.py --chip <target> --port <port> --baud <baud> write_flash <addr> <bin> [--flash_mode dio --flash_size detect]
esptool.py --chip <target> --port <port> read_mac
esptool.py --chip <target> --port <port> flash_id
idf.py -p <port> monitor                     # long-running
```

**Step 2 — parsing and validation.**

| Operation     | What proves it worked                                                                                                                                           |
| ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `write_flash` | exit code 0 **and** the literal string `Hash of data verified.` in stdout. Exit code alone is insufficient — a partial write can still exit 0 on some versions. |
| `read_mac`    | regex `MAC: ([0-9a-f]{2}:){5}[0-9a-f]{2}` — report the captured MAC, never a placeholder                                                                        |
| `flash_id`    | `Detected flash size: (\d+MB)`                                                                                                                                  |
| `monitor`     | nothing to assert synchronously — it's a stream                                                                                                                 |

**Step 3 — statefulness.** `write_flash`, `read_mac`, `flash_id` are one-shot. `idf.py monitor` is a session → background shell, identical in shape to `device-console-bridge` (its exit sequence is `Ctrl+]`, which the skill should document as the graceful stop before falling back to killing the shell).

**Step 4 — the skill.** A sketch of `espressif-flash-bridge/SKILL.md` (illustrative — not authored in this repo, since ESP-IDF is not this workspace's toolchain):

```
---
name: espressif-flash-bridge
description: Use when the user asks to flash, erase, or identify an ESP32-family
  chip with esptool, or monitor its console with idf.py. Triggers include "flash
  the esp32", "read the mac", "erase flash", "open the idf monitor".
---

## When to use
- Flashing a prebuilt .bin to an ESP32/S2/S3/C3/C6 over serial.
- Reading MAC / flash id for provisioning or board identification.
- Opening a monitor session on the device console.

## When NOT to use
- The board is a Zephyr target built with west -> use west-build-flash
  (Zephyr's esp32 runner wraps esptool for you; going around it desyncs
  the build's partition table).
- The user wants to build ESP-IDF sources -> that's `idf.py build`, a
  different skill.

## Required inputs
| Input          | Type                                              | Default                               |
| -------------- | ------------------------------------------------- | ------------------------------------- |
| action         | flash \| read-mac \| flash-id \| erase \| monitor | (ask)                                 |
| chip           | esp32 \| esp32s3 \| esp32c3 \| ...                | auto: `esptool.py --port <p> chip_id` |
| port           | serial device                                     | auto if exactly one /dev/ttyUSB*      |
| bin_path, addr | file + flash offset                               | (ask for flash)                       |
| baud           | int                                               | 460800                                |

## Procedure
1. Verify `which esptool.py`; verify `test -e <port>` and readability.
2. Resolve `chip` via chip_id if not given; print what was detected.
3. Run the templated command, capture stdout/stderr + exit code.
4. For flash: require BOTH exit 0 AND "Hash of data verified." before
   reporting success.
5. For monitor: background the shell, report the shell id as the session.

## Self-Validation Protocol
| #   | Check                         | How to verify                              |
| --- | ----------------------------- | ------------------------------------------ |
| 1   | esptool present               | `which esptool.py`                         |
| 2   | port exists + readable        | `test -r <port>`                           |
| 3   | exit code captured            | literal integer                            |
| 4   | flash verified                | grep -q "Hash of data verified." in stdout |
| 5   | MAC/flash-id came from stdout | the regex matched; value printed verbatim  |

## Retry policy
1 retry on "Failed to connect ... Wrong boot mode detected" after telling
the user to hold BOOT and tap EN. Never retry a verification mismatch.

## Output format / ## Examples
(same shape as the Zephyr skills)
```

Note how mechanical steps 1–4 were: the only genuinely vendor-specific knowledge is *"exit 0 is not enough; grep for `Hash of data verified.`"* — and that is exactly the knowledge an MCP wrapper would have encoded in Python, now written where a human can review it.

### The same recipe, other vendors

**STM32CubeProgrammer CLI.** Template: `STM32_Programmer_CLI -c port=SWD -w <file.bin> <addr> -v -rst` (or `port=COMx br=115200` for UART bootloader). Validation: `-v` makes verification explicit, so require the literal `File download complete` / `Verification...OK` strings plus exit 0. One-shot; no session. Gotcha to encode: the CLI returns 0 in some error paths, so string matching is mandatory, not optional.

**Nordic nRF Util / nrfjprog.** Template: `nrfutil device program --firmware <hex> --traits jlink` or legacy `nrfjprog --program <hex> --sectorerase --verify --reset`. Validation: exit code plus `--verify` output. `nrfutil device list` is the discovery equivalent of the port-resolution chain. RTT logging is already covered by `device-console-bridge` since it shells out to the same SEGGER tooling.

**TI UniFlash.** Template: `dslite.sh --config=<ccxml> <image>`. Validation: exit code plus `Program verification successful`. The `.ccxml` target-config file is a required input with no sensible default — a good example of an input the skill must *ask* for rather than guess.

**Microchip MPLAB IPE CLI.** Template: `ipecmd -TP<tool> -P<device> -F<hex> -M -OL`. Validation: parse the generated log file (it writes one) rather than stdout — an example of step 2 preferring the machine-readable artifact.

**SEGGER J-Link Commander.** Template: `JLinkExe -device <dev> -if SWD -speed 4000 -autoconnect 1 -CommanderScript <script.jlink>`. Encode the script-file pattern in the skill: J-Link Commander is interactive by default, and the scripted form is what makes it deterministic — exactly the kind of "the recipe is the value" knowledge that belongs in a skill.

In every case the conversion is the same three questions: *what argv, what proves it worked, is it a session?*

---

## 6. Where this sits in the extensibility ladder

Devin CLI (and equivalently Claude Code / Cursor / Windsurf) offers several extension layers. Choosing the right one matters:

| Layer                                     | What it is                                                      | Use it for                                                                                                                                                       |
| ----------------------------------------- | --------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Rules** (`AGENTS.md`, `.devin/rules/`)  | Always-on context injected every session                        | Project-wide standards: coding style, "always build with `--pristine`", "never push to main". Cheap but always consuming context.                                |
| **Skills** (`skills/<name>/SKILL.md`)     | On-demand procedures the agent invokes when the request matches | **MCP tool replacement.** Loaded only when relevant, so a dozen skills cost nothing until used.                                                                  |
| **Subagents** (`.devin/agents/<name>.md`) | Specialized worker profiles with their own prompt/tools         | Delegating long, self-contained work (e.g. "audit every driver in this subsystem") without polluting the main context.                                           |
| **Hooks** (`.devin/hooks.v1.json`)        | Shell commands or prompts fired on lifecycle events             | Policy enforcement: block `rm -rf` on the build tree, auto-run `checkpatch` after edits, log every flash to a file.                                              |
| **Plugins**                               | Git-distributed bundles of the above                            | Sharing this whole skill set with the team from one repo. Note plugin-declared MCP servers still obey the org's MCP toggle; the skills/rules/hooks parts do not. |
| **MCP servers**                           | External tool servers over a protocol                           | Genuinely remote/stateful services with auth (a hosted API, a database). Not needed for "run a local CLI".                                                       |

**Rule of thumb:** if the capability is *"run a local binary and interpret its output"*, it is a **skill**, and MCP was never buying you anything. If it is *"talk to a remote authenticated service that maintains state across sessions"*, MCP is the right tool — and if it is blocked by policy, the fallback is a skill that shells out to that service's own CLI (`gh`, `aws`, `az`, `jira`) or `curl`s its REST API.

For session state specifically, the pairing is: **skill** (the procedure) + **background shell** (the state), as described in section 4. Hooks are the layer to add if you want the session cleaned up automatically at the end of every conversation.

---

## 7. Migration checklist

To retire an MCP server of your own:

- [ ] List its registered tools (for FastMCP: grep for `mcp.tool()`).
- [ ] For each, extract the argv template and the env it needs (step 1).
- [ ] For each, extract what it checks to decide success (step 2). Note every place where the exit code is not sufficient.
- [ ] Group the tools: one skill per coherent workflow, not one skill per tool. (28 tools → 7 skills here, because `build`/`flash`/`build_flash`/`debugserver_*` are one workflow.)
- [ ] Mark the session-based ones; plan them as background shells (step 3).
- [ ] Author each `SKILL.md` with `embedded-skill-author` (step 4).
- [ ] Write the **When NOT to use** cross-references so skills route to each other instead of overlapping.
- [ ] Verify: every skill has all seven sections, its self-validation checks are literally executable, and no skill claims anything it cannot prove (step 5).
- [ ] Keep the old server around read-only for a while — it is the reference for the flags you encoded.

The original `zephyr_ai` source stays in this repo for exactly that reason: it is the spec these skills were derived from.
