---
name: devicetree-inspector
description: Use when the user asks what the devicetree actually resolved to after a build -- "which nodes are enabled", "is lpuart0 okay in the final DT", "what does the merged devicetree look like", "show me the chosen nodes", "did my overlay take effect", "list the i2c devices on this build". Reads the merged `zephyr.dts` (and `edt.pickle` when usable) from a build directory and reports enabled nodes, chosen entries, and aliases. Read-only -- never edits DT files.
---

# devicetree-inspector

Reports what the devicetree *actually became* after CMake merged the SoC dtsi, board dts, and overlays -- enabled nodes, `/chosen`, `/aliases`, and specific node lookups -- by reading the build directory's merged `zephyr.dts`. Answers "did my overlay take effect" with evidence rather than inference.

Replaces the `zephyr_ai` MCP tool: `parse_devicetree`.

## When to use

- User wants to confirm an overlay took effect (node now `status = "okay"`).
- User wants the list of enabled nodes, optionally filtered by compatible or label.
- User wants `/chosen` (e.g. `zephyr,console`, `zephyr,shell-uart`) or `/aliases` from the merged DT.
- User is about to write driver code and needs to know which peripheral instances are live.

## When NOT to use

- The user wants to *change* the devicetree (use `devicetree-author`).
- There is no build directory yet -- the merged DT only exists after a successful CMake configure (use `west-build-flash` first).
- The user is debugging a DT *error* that prevented the build (use `build-doctor`; a failed build has no merged `zephyr.dts`).
- The user wants Kconfig values rather than DT nodes (use `kconfig-tuner`).

## Required inputs

| Input | Type | Default |
|-------|------|---------|
| `query` | one of: `enabled-nodes`, `chosen`, `aliases`, `node`, `compatible`, `all` | `enabled-nodes` |
| `build_dir` | build directory containing `zephyr/zephyr.dts` | auto-detect (see below) |
| `dts_path` | explicit path to a merged `.dts`, used instead of `build_dir` | none |
| `node_label` | node label to look up (for `query = node`), e.g. `lpuart0`, `i2c1` | (required for `node`) |
| `compatible` | compatible string to filter by (for `query = compatible`), e.g. `nordic,nrf-uarte` | (required for `compatible`) |
| `max_rows` | rows printed before truncation | `60` |

## Build directory resolution

Try in order, take the first that resolves:

1. Explicit `dts_path`, if given and `test -f` passes.
2. Explicit `build_dir`, if `<build_dir>/zephyr/zephyr.dts` exists.
3. `./build/zephyr/zephyr.dts` relative to the current directory.
4. The most recently modified `*/zephyr/zephyr.dts` under `<workspace_root>/build/` (state which one was picked and its mtime).
5. Ask the user.

Never analyze source `.dts`/`.overlay` files as if they were the merged result -- an unmerged overlay tells you what was *requested*, not what the build produced. If only source files are available, say so explicitly and stop.

## Procedure

1. **Resolve the merged DTS.** Apply the chain above; verify with `test -f`. Report the path and its mtime so the user can tell whether it is stale relative to their last edit.
2. **Prefer `edt.pickle` only when it loads cleanly.** If `<build_dir>/zephyr/edt.pickle` exists, it may be unpicklable outside Zephyr's own Python environment (it needs `devicetree` modules on `sys.path`). Attempt it only if `python3 -c "import devicetree"` succeeds; otherwise skip straight to text parsing and state which backend was used. Never report a node count from a partially loaded pickle.
3. **enabled-nodes**: grep the merged DTS for `status = "okay"` and, for each hit, walk backwards to the nearest enclosing node header line to recover the node name and label. Report label, node path/name, and line number.
4. **chosen**: extract the `chosen { ... }` block verbatim and report each `zephyr,*` property with its target.
5. **aliases**: extract the `aliases { ... }` block verbatim and report each alias with its target.
6. **node**: locate `<node_label>:` in the merged DTS and print the full node body with its line range, including its `status`, `compatible`, `reg`, and any bus-child nodes.
7. **compatible**: grep for `compatible = "<compatible>"` and report every matching node with its label, line, and `status`.
8. **Report** with the output format below, truncating tables at `max_rows` while stating the true total.

## Self-Validation Protocol

Every check binary; report all five.

| # | Check | How to verify |
|---|-------|---------------|
| 1 | Merged DTS located | `test -f <dts_path>`; the path ends in `zephyr/zephyr.dts` or the user supplied it explicitly |
| 2 | Backend stated honestly | report exactly one of `edt_pickle` or `dts_text`; `edt_pickle` only after a successful load |
| 3 | Every reported "enabled" node is grep-verifiable | each reported line number in `<dts_path>` actually contains `status = "okay"` |
| 4 | Counts match | rows printed + truncated count == total grep hits |
| 5 | Staleness disclosed | the DTS mtime is reported so the user can judge whether it predates their latest edit |

If check 1 fails: halt and tell the user to build first. If check 3 fails for any row: drop that row and re-verify -- never report a node as enabled without the literal line backing it.

## Retry policy

If `edt.pickle` loading raises (missing `devicetree` module, version mismatch, unpickling error), fall back to text parsing **once** and clearly label the backend as `dts_text`. No further retries. If the merged DTS cannot be found, ask rather than searching the whole filesystem.

## Output format

```
devicetree-inspector report:

DTS:      /home/user/zephyrproject/build/hello_world_nrf52840dk/zephyr/zephyr.dts
Modified: 2026-08-22 10:14:07   (backend: dts_text)

Enabled nodes (status = "okay"): 24 total
  label        node                              line
  uart0        uart@40002000                     1187
  i2c0         i2c@40003000                      1244
  gpio0        gpio@50000000                     1302
  ...          (showing 60 of 24)

Chosen:
  zephyr,console    = &uart0
  zephyr,shell-uart = &uart0
  zephyr,sram       = &sram0

Validation:
  [x] merged DTS located:  zephyr/zephyr.dts
  [x] backend:             dts_text (edt.pickle skipped: devicetree module unavailable)
  [x] all rows grep-verified: 24/24 lines contain status = "okay"
  [x] counts match:        24 hits / 24 reported
  [x] staleness disclosed: mtime 2026-08-22 10:14:07
```

## Examples

### Example 1: did my overlay take effect

User: "I set `status = "okay"` on i2c1 in my overlay -- did it land?"

Agent resolves the newest build's `zephyr.dts`, greps for the `i2c1` node, and reports its resolved `status`, `compatible`, and line number, plus the DTS mtime so the user can confirm the build postdates the overlay edit. If the node is still `disabled`, it says so plainly and notes the overlay may not be in the build's `EXTRA_DTC_OVERLAY_FILE`/`DTC_OVERLAY_FILE` list.

### Example 2: which UART is the console

User: "which uart is the console on this build?"

Agent extracts the `chosen` block and reports `zephyr,console = &uart0`, then looks up `uart0` to report its `reg` and `status`.

### Example 3: refusal on source files only

User: "parse my board .dts" with no build directory present.

Agent refuses to present a source `.dts` as the resolved devicetree, explains that overlays and SoC dtsi includes are only merged at CMake configure time, and offers to build first via `west-build-flash`.

## Elevator pitch (for slides)

devicetree-inspector is the read-only half of DT work: it reports what the build actually produced, from the merged `zephyr.dts`, with every "enabled" claim backed by a grep-verifiable line number and the file's mtime disclosed so stale answers are visible. It never reads a source overlay and calls it the resolved devicetree.
