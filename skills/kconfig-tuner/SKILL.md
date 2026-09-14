---
name: kconfig-tuner
description: Use when the user asks to enable a Zephyr feature in plain English (shell, logging, I2C, USB, networking, etc.), or asks for the minimum CONFIG_* set for a goal. Triggers include "enable shell over UART", "turn on logging", "enable I2C support", "what configs do I need for X", "what should be in prj.conf for X". Translates English goals into a verified, minimal CONFIG_ diff and refuses to suggest any symbol that does not actually exist in the Zephyr Kconfig tree.
---

# kconfig-tuner

Translates plain-English Zephyr feature requests into a minimal, verified set of `CONFIG_*` symbols. Every suggested symbol is grep-verified against the Zephyr Kconfig tree before the agent reports it.

## When to use

- User wants to enable a Zephyr subsystem and asks "which configs do I need?"
- User pastes a `prj.conf` and asks "is this complete to enable X?"
- User asks for the minimum CONFIG set for a feature (shell, logging, I2C, USB, networking, sensor stack, etc.).

## When NOT to use

- The user is debugging an existing Kconfig dependency error (use `build-doctor`).
- The change is purely a device tree change (use `devicetree-author`).
- The user wants to invent a new Kconfig symbol (refuse: this skill never fabricates symbols).

## Required inputs

| Input | Type | Default |
|-------|------|---------|
| `goal` | English description of what to enable | (none -- ask) |
| `target_file` | path to the `prj.conf` or `_defconfig` to edit | (none -- ask) |
| `zephyr_root` | path to the Zephyr source tree | auto-detect (see Zephyr root resolution) |
| `modules_root` | path to the Zephyr modules tree (where `hal_*`, `mbedtls`, etc. live) | `<zephyr_root>/../modules` if it exists, else skip |
| `dry_run` | if true, propose the diff but do not write the file | false |

## Zephyr root resolution

Try in order, take the first that resolves:

1. `ZEPHYR_BASE` environment variable, if set and the directory exists.
2. `west topdir` if `west` is on PATH; the result is the workspace root, and `zephyr_root = <workspace>/zephyr`.
3. `/workdir/zephyr` (common container layout).
4. `./zephyrproject/zephyr` (common host layout).
5. Ask the user.

Report the resolved path back to the user once on first invocation.

## Procedure

1. **Parse the goal** into 1 or more candidate Kconfig symbols.
   - "shell over UART" -> `CONFIG_SHELL`, `CONFIG_SHELL_BACKEND_SERIAL`, `CONFIG_SERIAL`, `CONFIG_UART_CONSOLE`
   - "logging" -> `CONFIG_LOG`
   - "I2C" -> `CONFIG_I2C`
   - "BME280 sensor on I2C" -> `CONFIG_SENSOR`, `CONFIG_BME280`, `CONFIG_I2C`
2. **Verify each symbol exists** in the Zephyr tree. Run a single shell grep against `<zephyr_root>` (and `<modules_root>` if it resolved):

   ```
   grep -rl --include='Kconfig*' "^config <SYMBOL>$" <zephyr_root> [<modules_root>] 2>/dev/null | head -1
   ```

   If grep returns no result, the symbol does not exist. **Refuse to include unverified symbols. Never fabricate.**
3. **Construct the minimal diff.** Drop any symbol that the board's `_defconfig` (or, for a `prj.conf` target, an explicit board hint from the user) already sets to `y`. Keep only what the user must add.
4. **Optionally write to `target_file`.** If `dry_run` is true, just report.

## Self-Validation Protocol

| # | Check | How to verify |
|---|-------|---------------|
| 1 | Goal was parsed into >=1 candidate | the diagnosis lists at least one CONFIG_ symbol |
| 2 | Every proposed CONFIG_ symbol exists in the Zephyr tree | for each symbol, the grep above returns at least one path; the path is reported |
| 3 | No fabricated symbols | the count of (proposed) == count of (verified) |
| 4 | Target file exists if write was requested | `test -f <target_file>` before edit |
| 5 | Diff is minimal (no symbols already implied by board defconfig) | manual cross-check; report which were dropped |

If check 2 or 3 fails: the offending symbol must NOT be reported. Report only the verified subset, plus a note about the unverified ones with the suggestion to ask the user for guidance.

## Retry policy

No retries on symbol verification -- a missing symbol means the candidate was wrong, retrying produces the same answer. Drop and move on.

## Output format

```
kconfig-tuner result: PASS  (or FAIL)

Zephyr root:  /path/to/zephyr  (resolved via <ZEPHYR_BASE | west topdir | path>)

Goal: enable shell over UART

Proposed (verified) symbols:
  CONFIG_SHELL=y                     [defined in subsys/shell/Kconfig]
  CONFIG_SHELL_BACKEND_SERIAL=y      [defined in subsys/shell/backends/Kconfig.serial]
  CONFIG_SERIAL=y                    [defined in drivers/serial/Kconfig]
  CONFIG_UART_CONSOLE=y              [defined in drivers/console/Kconfig]

Already on by default for the target board: (none in this case)

Validation:
  [x] candidates parsed:    4 symbols
  [x] every symbol verified in Zephyr tree
  [x] no fabricated symbols
  [-] target_file exists:   (dry-run, no file requested)
  [x] minimal diff:         no symbols dropped as already-default
```

## Examples

### Example 1: enable shell over UART

User: "what do I need in prj.conf to get a shell prompt over the console?"

Output: 4 symbols (SHELL, SHELL_BACKEND_SERIAL, SERIAL, UART_CONSOLE), each verified.

### Example 2: refuse unverified

User: "enable CONFIG_FANCY_FEATURE"

Output: kconfig-tuner refuses. Symbol not found in Zephyr tree (verified via grep). Suggest the user check the spelling or find the closest matching real symbol.

## Elevator pitch (for slides)

kconfig-tuner translates plain-English Zephyr feature requests into a verified, minimal CONFIG_ diff. Every suggested symbol is grep-checked against the resolved Zephyr tree before being reported. Refusal to fabricate symbols is what separates this skill from a hallucination engine. Five binary checks per invocation.
