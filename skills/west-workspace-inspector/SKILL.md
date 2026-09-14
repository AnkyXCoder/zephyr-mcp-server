---
name: west-workspace-inspector
description: Use when the user asks about the shape of their Zephyr/west workspace -- "what workspace am I in", "what Zephyr version is this", "list the west projects/modules", "show me the resolved manifest", "which boards does this tree have", "list nordic boards", "what shields are available". Resolves the west workspace root and ZEPHYR_BASE, resolves the manifest via `west manifest --resolve`, reads the Zephyr VERSION file, and scans board.yml / shield.yml metadata. Read-only -- never builds, flashes, or edits files.
---

# west-workspace-inspector

Answers "what is this workspace?" questions about a Zephyr/west tree: workspace root, `ZEPHYR_BASE`, Zephyr version, resolved west manifest, project/module list, and available boards and shields. Every number reported is derived from a command that actually ran or a file that actually exists.

Replaces these `zephyr_ai` MCP tools: `detect_west_workspaces`, `analyze_workspace`, `analyze_west_workspace`, `get_zephyr_version`, `parse_west_manifest`, `list_modules`, `list_boards`.

## When to use

- User asks which west workspace / Zephyr tree is active, or wants it confirmed before a build.
- User wants the Zephyr version, the resolved manifest, or the list of west projects (modules) and their revisions.
- User wants to enumerate boards or shields, optionally filtered by vendor.
- Another skill needs the resolved `workspace_root` / `zephyr_root` before doing its own work.

## When NOT to use

- User wants to build or flash (use `west-build-flash`).
- User wants to diagnose a failed build (use `build-doctor`).
- User wants to know which `CONFIG_*` symbols exist (use `kconfig-tuner`).
- User wants devicetree node details from a build (use `devicetree-inspector`).
- User wants to create a new board (use `zephyr-bsp-scaffold`).

## Required inputs

| Input | Type | Default |
|-------|------|---------|
| `query` | one or more of: `workspace`, `version`, `manifest`, `modules`, `boards`, `shields`, `all` | `all` |
| `workspace_root` | path to the west workspace root (the directory containing `.west/`) | auto-detect (see below) |
| `zephyr_root` | path to the Zephyr source tree | `<workspace_root>/zephyr`, else auto-detect |
| `board_filter` | vendor name (`nordic`, `st`, `nxp`, `espressif`), `shields`, or `vendor:<name>` | none (no filter) |
| `max_rows` | maximum rows to print per table before truncating with a count | `50` |

## Workspace / Zephyr root resolution

Try in order, take the first that resolves:

1. `ZEPHYR_BASE` environment variable, if set and the directory exists → `zephyr_root`; `workspace_root = $(dirname $ZEPHYR_BASE)` if that directory contains `.west/`.
2. `west topdir` if `west` is on PATH → `workspace_root`; `zephyr_root = <workspace_root>/zephyr`.
3. Walk up from the current directory looking for a `.west/` directory.
4. `/workdir/zephyr` (common container layout).
5. `./zephyrproject/zephyr` (common host layout).
6. Ask the user.

Record which rule fired; report it in the output. Never guess silently.

## Procedure

1. **Resolve roots.** Apply the resolution chain above. Halt and ask the user if no rule resolves. Verify with `test -d <workspace_root>/.west` and `test -d <zephyr_root>`; if `.west/` is absent, report the tree as "Zephyr tree without a west workspace" rather than claiming a workspace.
2. **Version** (if `query` includes `version` or `all`): read `<zephyr_root>/VERSION`. Report the raw contents. If the file is absent, say so; do not infer a version from a git tag unless the user asks.
3. **Manifest** (if `query` includes `manifest`, `modules`, or `all`): run `west manifest --resolve` with the working directory set to `workspace_root`. If exit code is non-zero, report the stderr verbatim and stop the manifest branch -- do not fall back to reading `west.yml` directly and present it as "resolved".
4. **Modules / projects** (if `query` includes `modules` or `all`): from the resolved manifest YAML, take `manifest.projects[]` and report `name`, `path`, `revision`, and `url` for each. Compute `path` as `<workspace_root>/<project.path>` and mark whether that directory currently exists on disk.
5. **Boards and shields** (if `query` includes `boards`, `shields`, or `all`): scan `<zephyr_root>/boards/*/*/board.yml` and `<zephyr_root>/boards/shields/*/*/shield.yml`. For boards, read `name`, `full_name`, `vendor`, and `socs` from the YAML, falling back to the directory names when a key is absent. Apply `board_filter` if given (`shields` = shields only; `vendor:<name>` or a bare vendor alias = exact vendor match, with the aliases `stm`/`st` → `st`, `esp` → `espressif`).
6. **Report** using the output format below, truncating each table at `max_rows` and stating the true total.

## Self-Validation Protocol

Every check binary; report all five.

| # | Check | How to verify |
|---|-------|---------------|
| 1 | Workspace root resolved and exists | `test -d <workspace_root>`; note which resolution rule fired |
| 2 | Zephyr root resolved and is a Zephyr tree | `test -f <zephyr_root>/VERSION` or `test -d <zephyr_root>/boards` |
| 3 | `west manifest --resolve` exit code captured | record the literal exit code; a non-zero code must be reported, never hidden |
| 4 | Project count matches the parsed manifest | count of rows printed + truncated count == `len(manifest.projects)` |
| 5 | Board/shield counts come from real files | each reported entry has an existing `board.yml`/`shield.yml`; if the scan finds zero, report "none found" explicitly rather than an empty table |

If check 1 or 2 fails: halt and ask the user for the path. Never report data from a tree you could not verify.

## Retry policy

If `west manifest --resolve` fails because `west` is not on PATH, retry once after sourcing a workspace-local virtualenv if one is obvious (`<workspace_root>/.venv/bin/activate` or `<workspace_root>/../.venv/bin/activate`). Maximum 1 retry. If it still fails, report the manifest section as unavailable and continue with the remaining sections.

## Output format

```
west-workspace-inspector report:

Workspace root: /home/user/zephyrproject          (resolved via: west topdir)
Zephyr root:    /home/user/zephyrproject/zephyr
Zephyr version: VERSION_MAJOR=4 VERSION_MINOR=3 PATCHLEVEL=0 ...

Manifest (west manifest --resolve, exit 0): 42 projects
  name            path                      revision
  hal_nordic      modules/hal/nordic        a1b2c3d      [on disk]
  cmsis           modules/hal/cmsis         e4f5a6b      [on disk]
  ...             (showing 50 of 42)

Boards (filter: nordic): 37 matches
  name                 vendor    socs           dir
  nrf52840dk           nordic    nrf52840       boards/nordic/nrf52840dk
  ...

Shields: 214 total

Validation:
  [x] workspace root exists:   /home/user/zephyrproject (rule 2: west topdir)
  [x] zephyr root verified:    VERSION present
  [x] west manifest exit code: 0
  [x] project count matches:   42 parsed / 42 reported
  [x] board entries verified:  37 board.yml files exist
```

## Examples

### Example 1: confirm the workspace before a build

User: "which Zephyr am I actually building against?"

Agent resolves `ZEPHYR_BASE` (rule 1), reports the root, the VERSION contents, and notes that `.west/` exists one level up so the workspace root is the parent. Validation table shows all five checks green.

### Example 2: list boards for one vendor

User: "list the nordic boards in this tree"

Agent scans `<zephyr_root>/boards/nordic/*/board.yml`, reports name/full_name/socs per board and the true total, truncating the table at `max_rows`. If a `board.yml` is missing a `vendor:` key, the vendor is taken from the parent directory name and that inference is stated in a footnote.

### Example 3: manifest unavailable

User: "show me the resolved manifest" but `west` is not installed.

Agent retries once with a workspace-local venv, then reports: `west manifest --resolve` unavailable (`west: command not found`), manifest section skipped. It does NOT read `west.yml` and present it as resolved -- an unresolved manifest lacks imported projects and would be misleading.

## Elevator pitch (for slides)

west-workspace-inspector answers "what workspace am I in?" the way an MCP `analyze_workspace` tool would -- resolved root, Zephyr version, resolved manifest, project list, boards and shields -- but as a Devin CLI skill built on `exec`, `read`, and `grep`. Five binary checks make every count falsifiable, and a failed `west manifest --resolve` is reported, never papered over.
