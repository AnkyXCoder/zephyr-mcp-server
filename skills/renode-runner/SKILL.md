---
name: renode-runner
description: Use when the user asks to run a built Zephyr ELF under Renode, or asks to verify that a sample boots in simulation, or says any of "run hello world in renode", "test under renode", "renode hello", "verify in simulation". Wraps Renode invocation, UART log capture, and expected-string assertion. Returns PASS or FAIL with a structured validation table.
---

# renode-runner

Runs a Zephyr ELF on a Renode platform and asserts that an expected console string appears on UART within a timeout. Returns PASS / FAIL with a structured validation table.

## When to use

- User asks to run a sample under Renode and wants pass/fail on simulated UART output (e.g. "Hello World", "*** Booting Zephyr").
- User wants a determinism gate around a Renode-emulated scenario (CI smoke, regression check).

## When NOT to use

- The user has real hardware connected and wants to flash. Use the chip vendor's flash tool (LinkServer, JLink, OpenOCD, etc.) instead.
- The peripheral the sample exercises is not modeled in the platform `.repl`. Read the `.repl` first; if the peripheral is missing, refuse and tell the user.
- The ELF was built for a different SoC family than the platform `.repl` describes. Confirm the `west build -b` target matches the platform.

## Required inputs

The agent MUST collect these before invoking Renode. If any are missing, ask the user.

| Input | Type | Default |
|-------|------|---------|
| `elf_path` | absolute or workspace-relative path to `zephyr.elf` | `build/zephyr/zephyr.elf` |
| `scenario_resc` | path to the Renode scenario script (`.resc`) | (none -- ask) |
| `expected_string` | string that must appear in UART log | (none -- ask) |
| `uart_path` | the Renode peripheral path of the console UART (used for `CreateFileBackend`) | `sysbus.lpuart0` (override per platform) |
| `log_path` | where to write the captured UART log | `renode/logs/run.uart` |
| `timeout_seconds` | integer | `10` |
| `renode_invocation` | how to launch Renode | auto-detect (see below) |

## Renode invocation resolution

For step 4 of the procedure:

1. If `renode --version` succeeds on the host, use bare `renode --console --disable-xwt`.
2. Otherwise, if `docker-compose.yml` exists and a service has Renode installed, use `docker compose run --rm <service> renode --console --disable-xwt`.
3. Otherwise, ask the user how to launch Renode.

When using a containerized invocation, the agent MUST translate workspace-relative ELF, .resc, and log paths into the container's mount path (e.g. `/workdir/app/<rel>`).

## Procedure

Execute these steps in order. Each step has an explicit halt condition.

1. **Verify ELF.** `test -f <elf_path>`. If missing, halt with "ELF not found at <path>; build first with `west build`".
2. **Verify .resc.** `test -f <scenario_resc>`. If missing, halt with "scenario script not found".
3. **Prepare UART log path.** `mkdir -p $(dirname <log_path>) && rm -f <log_path>`.
4. **Invoke Renode** via the resolved `renode_invocation`:
   ```
   timeout <timeout_seconds + 4> <renode_invocation> \
       -e '$bin=@<elf_path>' \
       -e 'i @<scenario_resc>' \
       -e '<uart_path> CreateFileBackend @<log_path> true' \
       -e 'start' -e 'sleep <timeout_seconds>' -e 'quit'
   ```
   For containerized runs the agent prepends the container mount path to the `@`-paths.
5. **Check UART log.** `grep -q '<expected_string>' <log_path>`.
6. **Report.** Print the validation table (see below) and PASS or FAIL.

## Self-Validation Protocol

Before declaring success, the agent MUST execute and report on every check below. Each check is binary.

| # | Check | How to verify |
|---|-------|---------------|
| 1 | ELF file exists | `test -f <elf_path>` exits 0 |
| 2 | Scenario .resc exists | `test -f <scenario_resc>` exits 0 |
| 3 | Renode invocation completed | invocation exit code is 0 (or 124 from outer `timeout`, which is expected when `sleep N` is the runner) |
| 4 | UART log was written | `test -s <log_path>` exits 0 |
| 5 | Expected string is in UART log | `grep -q '<expected_string>' <log_path>` exits 0 |

If checks 1-4 pass but check 5 fails: this is a real failure (Zephyr booted but the sample did not produce the expected output). Report FAIL and include the last 20 lines of the UART log so the user can diagnose.

If check 1 or 2 fails: halt and tell the user what to do (build the ELF; provide a valid `.resc` path).

If check 3 fails: examine the launcher error. Common causes (containerized runs): container image not built, Docker daemon not running. Common causes (native): `renode` not on PATH.

If check 4 passes but check 5 fails after one full run: retry once with `timeout_seconds + 5` in case the sample is slow to print. If it still fails, report FAIL.

## Retry policy

Maximum 1 retry, only on check 5 failure (UART non-empty but no expected string). Retry uses `timeout_seconds + 5`. After the retry attempt, escalate to the user with the captured log.

## Output format

The agent MUST end every invocation with this structure:

```
renode-runner result: PASS  (or FAIL)

Validation:
  [x] ELF exists:       <elf_path>
  [x] Scenario script:  <scenario_resc>
  [x] Renode completed: exit 0
  [x] UART log written: <log_path> (1842 bytes)
  [x] Expected string:  "<expected_string>" found

UART log (last 5 lines):
  *** Booting Zephyr OS build v4.4.0 ***
  Hello World! <board>/<soc>
```

For FAIL, replace the corresponding `[x]` with `[ ]` and add a "Cause:" line below the table.

## Examples

### Example 1: hello_world on a custom platform

User: "run hello world on my Renode platform and check for the boot banner"

Agent inputs:
- `elf_path` = `build/zephyr/zephyr.elf`
- `scenario_resc` = `renode/scripts/single-node/<my_platform>_hello_world.resc`
- `expected_string` = `Hello World`
- `timeout_seconds` = 10

### Example 2: refuse on missing peripheral

User: "run an Ethernet test in renode"

Agent: "Ethernet is not modeled in your platform .repl. Open the .repl and confirm the peripheral is registered before retrying, or pick a scenario that exercises a modeled peripheral."

## Elevator pitch (for slides)

renode-runner takes a built Zephyr ELF and a Renode scenario script, runs the simulation, captures UART output, and returns PASS / FAIL against an expected string. Five binary checks (ELF, .resc, launcher exit, log written, expected string) make the determinism story explicit.
