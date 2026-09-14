---
name: build-doctor
description: Use when a `west build` has failed or the user pastes a build error and asks why. Triggers include "diagnose this build error", "why did the build fail", "fix this build", "build broke", "build-doctor", or any pasted west/cmake/dtc error message. Reads captured stderr (or runs a fresh build), classifies the failure into one of five categories, and produces a structured diagnosis with the offending file, line, and a specific fix.
---

# build-doctor

Reads a failed `west build`'s stderr, classifies the failure into one of five known categories, names the file and line at fault, and proposes a specific fix that references real files in the Zephyr tree.

## When to use

- `west build` exited non-zero and the user wants the cause and fix.
- The user pastes a Zephyr/CMake/dtc error and asks for help.
- A verification step fails after a config or DT change.

## When NOT to use

- The build succeeded but the *behavior* on hardware or in simulation is wrong (use `renode-runner` for sim assertions, hardware debug for board issues).
- The error is in skill execution, not in `west build` (those are not classifiable here).

## Required inputs

| Input | Type | Default |
|-------|------|---------|
| `stderr` | path to a file containing captured stderr from `west build`, or the stderr inline | (one of these is required) |
| `project_path` | optional: path to a Zephyr project to build fresh | none |
| `zephyr_root` | path to the Zephyr source tree (used to validate fix-referenced files) | auto-detect (see below) |

If `stderr` is provided, work from it. If not but `project_path` is, run `west build` against the project and capture stderr. If neither, ask the user.

## Zephyr root resolution

Try in order, take the first that resolves:

1. `ZEPHYR_BASE` environment variable, if set and the directory exists.
2. `west topdir` if `west` is on PATH; the result is the workspace root, and `zephyr_root = <workspace>/zephyr`.
3. `/workdir/zephyr` (common container layout).
4. `./zephyrproject/zephyr` (common host layout).
5. Ask the user.

## The five failure categories

The skill MUST classify every failure into exactly one of these. If the symptoms span multiple, pick the one that fires earliest in the toolchain (DT before Kconfig before CMake before linker).

| Category | Signature | Typical first-line in stderr |
|----------|-----------|------------------------------|
| **missing-binding** | DT node has a `compatible` string with no matching binding YAML | `'compatible' value '<x>' has no binding` or `error: <x>: undefined compatible` |
| **undefined-node-label** | DT references `&label` but no node defines that label | `Reference to undefined label '<x>'` |
| **kconfig-dep** | A CONFIG symbol depends on another CONFIG that is not enabled, or a symbol does not exist | `warning: ... symbol .* has direct dependencies` or `error: undefined symbol CONFIG_<x>` |
| **dtc-error** | Device tree compiler reports a syntax/structural error | `Error: <file>.dts:<line>: ...` from dtc |
| **cmake-error** | CMakeLists.txt or CMake configuration fails before the kernel build starts | `CMake Error at <file>:<line>` |

If none match: report `category: unknown` and dump the first 30 lines of stderr verbatim. Do not invent a category.

## Procedure

1. **Acquire stderr.** If `stderr` is a file, read it. If inline, capture into a temp file. If `project_path` only, run `west build` and tee stderr.
2. **Scan for category signatures.** Use grep for the regexes in the table above, in the priority order DT bindings -> labels -> Kconfig -> dtc -> cmake.
3. **Locate the offending file and line.** Most Zephyr errors include a path and line number. Capture both.
4. **Verify the fix references real files.** Whatever fix you propose, every file you cite must exist on disk. Run `test -f <path>` for each before including it in the diagnosis. The Zephyr tree lives at the resolved `zephyr_root`.
5. **Produce the diagnosis** in the structured format below.

## Self-Validation Protocol

Every check binary; report all five.

| # | Check | How to verify |
|---|-------|---------------|
| 1 | stderr was acquired (non-empty) | `test -s <stderr_file>` |
| 2 | Exactly one category was assigned | grep `^Category: ` in the diagnosis output, count == 1 |
| 3 | Category is one of the five (or `unknown`) | match against allowed set |
| 4 | Offending file path exists OR is in the user's project tree | `test -f <path>` for absolute paths; for relative paths, `test -f <project_root>/<path>` |
| 5 | If a fix references a Zephyr binding YAML or Kconfig, the cited path exists | `test -f <zephyr_root>/<path>` |

If check 4 or 5 fails: do NOT report the diagnosis as final. Re-scan and find a path that does exist, or honestly state "could not locate offending file in the user's project; the error pattern is X but path resolution failed". Never fabricate a path.

## Retry policy

If category classification is `unknown` after the first pass: re-read stderr more carefully (it may include multiple errors; pick the EARLIEST one). Maximum 1 re-classification attempt. If still unknown, report unknown.

## Output format

```
build-doctor diagnosis:

Category: missing-binding
Offending file: <relative or absolute path>:<line>
Root cause: <one sentence>

Fix:
  <specific actionable step, with file paths that exist>

Validation:
  [x] stderr acquired:   /tmp/build.err (1842 bytes)
  [x] category assigned: missing-binding
  [x] valid category:    yes (1 of 5 known)
  [x] file exists:       overlay.dts
  [x] cited binding YAML: <zephyr_root>/dts/bindings/sensor/bosch,bme280-i2c.yaml exists
```

## Examples

### Example 1: missing-binding

User pastes:
```
'compatible' value 'bosch,bme280-spi' has no binding
```

Diagnosis:
- Category: missing-binding
- Cause: the overlay declares `compatible = "bosch,bme280-spi"` but no binding YAML by that name exists at `<zephyr_root>/dts/bindings/sensor/`. The vendor's `bosch,bme280` binding loads via the bus parent (i2c-spi-bus) instead.
- Fix: change overlay to `compatible = "bosch,bme280"` (Zephyr selects the i2c or spi flavor based on the parent bus node).

### Example 2: undefined-node-label

User pastes:
```
Reference to undefined label 'lpuart7'
```

Diagnosis:
- Category: undefined-node-label
- Cause: the dts uses `&lpuart7` but no node with `lpuart7:` exists in the merged device tree. Either the SoC dtsi does not define this peripheral, or the label is misspelled.
- Fix: enumerate the available labels for the target SoC by grepping the merged DT (`<build_dir>/zephyr/zephyr.dts`) for `lpuart` and pick one that is not already in use as the console.

## Elevator pitch (for slides)

build-doctor classifies a failed `west build` into one of five categories (missing binding, undefined label, kconfig dependency, dtc error, cmake error), names the file and line, and proposes a fix that references real files in the resolved Zephyr tree. Five binary checks make every diagnosis falsifiable.
