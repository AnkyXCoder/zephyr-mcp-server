---
name: zephyr-bsp-scaffold
description: Use when the user asks to scaffold, create, or bring up a new Zephyr board from a reference, or says any of "scaffold the board", "create a new BSP", "scaffold a new board variant", "set up a custom board". Mirrors a Zephyr board's layered set of files (the .dts and supporting .dtsi, Kconfig.defconfig, _defconfig, board.cmake, board.yml metadata, plus optional Kconfig.<board>, board.c, pinctrl.dtsi) from a reference directory into a new target directory, renaming identifiers where the new board name appears.
---

# zephyr-bsp-scaffold

Generates a working Zephyr board scaffold by mirroring a known-good reference BSP, renaming the board identifier where it appears, and leaving the SoC binding intact. The output is a directory that `west boards` can list and `west build` can use.

## When to use

- User asks to scaffold or bootstrap a new board variant from an existing one.
- User names a target board name and points at a reference BSP directory.

## When NOT to use

- The user wants to *modify* an existing board (use `devicetree-author` for DT changes, `kconfig-tuner` for CONFIG changes).
- The user has not specified a reference path. Ask for one before proceeding.
- The reference path does not exist on disk. Halt and tell the user.

## Required inputs

| Input | Type | Default |
|-------|------|---------|
| `target_name` | new board name (e.g. `frdm_mcxa156_workshop`, `nucleo_l4r5zi_lab`) | (none -- ask) |
| `reference_path` | path to the reference BSP directory | (none -- ask) |
| `target_dir` | where to write the new BSP | `$(dirname <reference_path>)/<target_name>` |
| `reference_board_name` | the existing identifier to rename (e.g. `frdm_mcxa156`, `nucleo_l4r5zi`) | inferred from `<reference_path>`'s `board.yml` |
| `soc_qualifier` | the Zephyr build qualifier suffix after the slash (e.g. `mcxa156`, `stm32l4r5xx`) | inferred from `<reference_path>/board.yml`'s `socs.name` |
| `project_path` | a Zephyr project to use for the post-scaffold smoke build | defaults to a hello_world sample inside the resolved Zephyr workspace |
| `zephyr_root` | path to the Zephyr source tree | auto-detect (see below) |
| `build_invocation` | how to run `west build` for smoke validation | auto-detect (see below) |

The new board's SoC stays as the reference SoC -- this skill changes board identity, not silicon.

## Zephyr root resolution

Try in order, take the first that resolves:

1. `ZEPHYR_BASE` environment variable, if set.
2. `west topdir` if `west` is on PATH; `zephyr_root = <workspace>/zephyr`.
3. `/workdir/zephyr` (common container layout).
4. `./zephyrproject/zephyr` (common host layout).
5. Ask the user.

## Build-invocation resolution

1. If `west` is on PATH, run `west build` directly.
2. Otherwise, look for a project-local container wrapper script (e.g. `./build.sh`).
3. Otherwise, if a `docker-compose.yml` exists, use `docker compose run --rm <service> west build`.
4. Otherwise, ask the user.

## Procedure

Execute these steps in order. Do not skip; the self-validation depends on each.

1. **Resolve and report the Zephyr workspace.** Resolve `<zephyr_root>` via the standard chain (`$ZEPHYR_BASE` → `west topdir` → common defaults → ask). **Report the resolved path explicitly in the output before proceeding.** If the resolution is ambiguous (multiple `$ZEPHYR_BASE`-like candidates, a `west topdir` that disagrees with a sibling `.west/`, or any sign of more than one Zephyr workspace on the system), list every candidate and halt-and-ask. The user must see which workspace the scaffold is sourcing from before mirroring.

2. **Enumerate all reference BSPs that natively cover the target SoC.** Search `<zephyr_root>/boards/` tree-wide for `.dts` basenames that contain the target `soc_qualifier`. Use a basename grep across all vendor namespaces; do NOT filter by chip-family brand name. A brand like "Raspberry Pi" in the user's prompt is descriptive of silicon, not a constraint on the vendor directory — e.g., Pimoroni and Adafruit boards also use RP-series silicon and are valid references.

   Three branches:
   - **0 candidates.** Halt. Tell the user the resolved workspace contains no native reference for the target SoC. Recommend: (a) point at a different workspace, (b) specify a reference BSP path explicitly, or (c) abort.
   - **1 candidate.** Report it and confirm with the user before mirroring.
   - **2+ candidates.** List them and ask which to use.

   Once the user has confirmed, record `reference_path`, `reference_board_name`, and `soc_qualifier` explicitly in the output for the rest of the procedure.

3. **Never adapt a reference to a different SoC.** The mirrored reference's `.dts` / `.yaml` / `_defconfig` basenames MUST already contain the chosen `soc_qualifier`. Do NOT mirror an adjacent reference and then substitute the qualifier in basenames, edit the SoC `#include`, or "fix up" pin assignments to match a different silicon. Pin maps, package sizes, peripherals, and clocks differ between variants in non-obvious ways that the build will not catch (the smoke build often only exercises hello_world). If you cannot find a natively-matching reference in step 2, halt — do not adapt.

4. **Verify target empty.** `test -z "$(ls -A <target_dir> 2>/dev/null)"`. If non-empty, halt and ask whether to overwrite.

5. **Mirror the directory tree.** `cp -R <reference_path>/. <target_dir>/`. This copies all files and subdirectories.

   **External `common/` directory check.** Some references (notably Raspberry Pi: `boards/raspberrypi/rpi_pico2` `#include`s `../common/rpi_pico-led.dtsi`) depend on a sibling `common/` directory at `<dirname(reference_path)>/common/`. After mirroring, grep the copied dtsi files for `#include "../common/` — if any match, you have three options to report to the user:
   - (a) copy the cited sibling files into the target so the BSP is self-contained,
   - (b) inline the included content into the board's dtsi, or
   - (c) accept that the target board still depends on the upstream `common/` and document it.

   Default: report the dependency and ask. Do not silently break the link.

6. **Rename files whose basename includes `<reference_board_name>`.** Two layouts exist; detect which the reference uses:

   **Single-variant layout** (e.g. `frdm_mcxa156`): one of each file, no SoC qualifier in the basename.
   - `Kconfig.<reference_board_name>` -> `Kconfig.<target_name>`
   - `<reference_board_name>.dts` -> `<target_name>.dts`
   - `<reference_board_name>.yaml` -> `<target_name>.yaml`
   - `<reference_board_name>_defconfig` -> `<target_name>_defconfig`

   **Multi-qualifier layout** (Zephyr hwmv2; e.g. `rpi_pico2_rp2350a_m33`, `rpi_pico2_rp2350a_hazard3`): the reference has one `.dts` / `.yaml` / `_defconfig` triple per SoC/core qualifier, and the basename is `<reference_board_name>_<qualifier_underscored>`. Identify the variant the user wants and rename ONLY that triple to `<target_name>_<qualifier_underscored>.{dts,yaml}` and `<target_name>_<qualifier_underscored>_defconfig`. Delete or leave-untouched the other variants per the user's instruction. The plain-name fallback (`<target_name>.dts`) does NOT work for hwmv2 boards — Zephyr will silently fall back to `boards/common/stub.dts` and produce an empty resolved DT.

   Do NOT rename pinctrl.dtsi files that the reference's `.dts` includes by name (e.g. `<reference_board_name>-pinctrl.dtsi`). The new `.dts` continues to `#include` that file by its original name.

7. **Edit `board.yml`.** Change the `name:` field from `<reference_board_name>` to `<target_name>`. Leave `full_name`, `vendor`, and `socs.name` untouched. For multi-qualifier references, also trim the `socs:` / `variants:` lists so only the target's variant is exposed (otherwise `west boards` lists phantom variants whose files no longer exist).
8. **Edit `Kconfig.<target_name>`.** Replace the symbol `BOARD_<UPPERCASE(reference_board_name)>` with `BOARD_<UPPERCASE(target_name)>` everywhere it appears. Keep the `select SOC_*` and `select SOC_PART_NUMBER_*` lines unchanged.
9. **Edit the board-symbol-defining Kconfig.** Most references have a plain `Kconfig` file that contains `config BOARD_<UPPERCASE(reference_board_name)>` to wire up `BOARD_EARLY_INIT_HOOK` (and similar). Some references (notably Raspberry Pi) put that block in `Kconfig.defconfig` instead and ship no plain `Kconfig`. Locate whichever file contains the `config BOARD_<UPPERCASE(reference_board_name)>` block and replace that symbol with `BOARD_<UPPERCASE(target_name)>`. Without this step, Kconfig sees a symbol referenced by the named-Kconfig but never defined, and the build aborts.
10. **Edit `<target_name>.yaml`** (or `<target_name>_<qualifier_underscored>.yaml` for hwmv2). Change the `identifier:` field from `<reference_board_name>/<soc_qualifier>` to `<target_name>/<soc_qualifier>`. Change the `name:` field similarly.
11. **Run self-validation** (next section).

## Self-Validation Protocol

The agent MUST execute every check below and report each binary outcome.

| # | Check | How to verify |
|---|-------|---------------|
| 1 | Reference path is a directory | `test -d <reference_path>` exits 0 |
| 1a | Zephyr workspace resolved + reported | `<zephyr_root>` is echoed in the output before mirroring. If the resolution was ambiguous, the user explicitly confirmed which workspace. |
| 1b | Reference natively covers the target SoC | The mirrored reference's basenames contained the chosen `soc_qualifier` BEFORE any rename (i.e., `<reference_path>/*<soc_qualifier_underscored>*.dts` matches at least one file). If the agent had to substitute the qualifier into basenames or includes during step 6, this check FAILS — the reference was not a valid candidate. |
| 1c | Reference candidates enumerated tree-wide | Step 2's search covered `<zephyr_root>/boards/` across all vendor namespaces; the agent's output names the search command used. If only one vendor namespace was searched (e.g., brand-name heuristic), this check FAILS. |
| 1d | SoC variant chosen unambiguously | Either step 2 found exactly one candidate, OR the user explicitly confirmed which candidate after step 2's enumeration. The chosen `reference_path`, `reference_board_name`, and `soc_qualifier` are echoed back. |
| 2 | Target directory was created and is non-empty | `test "$(ls -A <target_dir> | wc -l)" -ge 6` |
| 3 | Required files present | Always: `board.yml`, `Kconfig.<target_name>`, `board.cmake` exist. For single-variant: also `<target_name>.dts`, `<target_name>_defconfig`. For multi-qualifier (hwmv2): also `<target_name>_<qualifier_underscored>.dts`, `<target_name>_<qualifier_underscored>.yaml`, `<target_name>_<qualifier_underscored>_defconfig`. The base `Kconfig` is OPTIONAL — some references (Raspberry Pi) put the board symbol in `Kconfig.defconfig` only. |
| 4 | board.yml has the new name | `grep -q "name: <target_name>" <target_dir>/board.yml` |
| 5a | Named Kconfig has renamed symbol | `grep -q "BOARD_<UPPERCASE(target_name)>" <target_dir>/Kconfig.<target_name>` |
| 5b | Board-symbol-defining Kconfig has renamed symbol | `grep -q "config BOARD_<UPPERCASE(target_name)>" <target_dir>/Kconfig <target_dir>/Kconfig.defconfig 2>/dev/null` — i.e. the symbol is defined in EITHER the plain `Kconfig` or in `Kconfig.defconfig`. Both layouts pass. |
| 5c | External `common/` dependencies surfaced | If step 3 detected `#include "../common/..."` in mirrored dtsi files: `grep -q "common/" <target_dir>/*.dtsi` and the agent's report names which files and the resolution chosen (copy / inline / accept upstream dependency) |
| 6 | west lists the new board | `<build_invocation_root> west boards --board-root <board_root>` lists `<target_name>` |
| 7 | CMake configure succeeds | `<build_invocation> -p always -b <target_name>/<soc_qualifier> <project_path> -d /tmp/scaffold-build -- -DBOARD_ROOT=<board_root>` exits 0 |

`<board_root>` is the workspace root directory that contains `boards/`. For a containerized setup, the agent translates this into the container's mount path.

If checks 1, 1a, 1b, 1c, or 1d fail: stop and ask the user. These are pre-mirror gates; do not proceed past them by substituting or adapting.
If check 2 fails: stop and ask the user.
If checks 3-5 fail: the file rename or content edit was wrong; review and correct.
If check 5c fails: the BSP is not self-contained; the agent must surface the `common/` dependency to the user and propose copy / inline / accept.
If check 6 fails but 3-5 pass: BOARD_ROOT is misconfigured or board.yml is malformed.
If check 7 fails: report the build error and invoke `build-doctor` if available. Note that check 7 failures are often *environmental* (Zephyr-version / SDK-version mismatch, missing toolchain components) rather than scaffold defects — the agent should verify by attempting the same build against the unmodified reference board and report whether it fails identically.

## Retry policy

No automatic retries. Each check is deterministic; on failure, the agent reports the exact failure mode so the user can intervene.

## Output format

```
zephyr-bsp-scaffold result: PASS  (or PARTIAL / FAIL)

Layout detected: single-variant (or multi-qualifier hwmv2)
Reference variant mirrored: <reference_board_name>[_<qualifier>]

Validation:
  [x] Reference exists:           <reference_path>
  [x] Target populated:           <target_dir>  (12 files)
  [x] Required files:             board.yml, Kconfig.<target_name>, <variant_files>, board.cmake
  [x] board.yml renamed:          name: <target_name>
  [x] Named Kconfig symbol:       BOARD_<UPPERCASE(target_name)>
  [x] Board-defining Kconfig:     symbol found in <Kconfig | Kconfig.defconfig>
  [x] common/ deps surfaced:      none (or: copied / inlined / accepted upstream)
  [x] west boards lists:          <target_name>
  [x] CMake configure:            hello_world built (FLASH 1.71 %)
```

## Examples

### Example 1: scaffold an MCXA-based variant

User: "scaffold frdm_mcxa156_workshop from boards/nxp/frdm_mcxa156_reference"

Inputs collected:
- `target_name` = `frdm_mcxa156_workshop`
- `reference_path` = `boards/nxp/frdm_mcxa156_reference`
- `reference_board_name` = `frdm_mcxa156` (inferred from board.yml)
- `soc_qualifier` = `mcxa156` (inferred from board.yml)
- `target_dir` = `boards/nxp/frdm_mcxa156_workshop` (derived)

### Example 2: scaffold from an hwmv2 multi-qualifier reference (RP2350)

User: "scaffold per_301 from zephyr/boards/raspberrypi/rpi_pico2, m33 variant"

Inputs collected:
- `target_name` = `per_301`
- `reference_path` = `<workspace>/zephyr/boards/raspberrypi/rpi_pico2`
- `reference_board_name` = `rpi_pico2_rp2350a_m33`
- `soc_qualifier` = `rp2350a/m33`
- `target_dir` = `.` (CWD)

Layout detected: **multi-qualifier (hwmv2)**. Reference has four `.dts`/`.yaml`/`_defconfig` triples — hazard3 / m33 / m33_w / m33_mcuboot. Mirror only the m33 triple.

After step 3, the agent grepped the mirrored dtsi files and found `#include "../common/rpi_pico-led.dtsi"` and `#include "../common/rpi_pico-pinctrl-common.dtsi"` — the reference depends on a sibling `common/` directory. Agent halts, surfaces the dependency, and asks: copy / inline / accept upstream link?

Files renamed:
- `rpi_pico2_rp2350a_m33.dts` -> `per_301_rp2350a_m33.dts`
- `rpi_pico2_rp2350a_m33.yaml` -> `per_301_rp2350a_m33.yaml`
- `rpi_pico2_rp2350a_m33_defconfig` -> `per_301_rp2350a_m33_defconfig`

`Kconfig.defconfig` (this reference has no plain `Kconfig`) gets the `BOARD_PER_301` rename. `board.yml` is trimmed so only the m33 variant remains.

### Example 3: refuse on missing reference

User: "scaffold a board from boards/foo/bar"

Agent: "boards/foo/bar does not exist. Specify a reference BSP directory that does."

## Elevator pitch (for slides)

zephyr-bsp-scaffold takes a reference BSP and a new board name, mirrors the full layered set of board files into a fresh directory, and renames the board identifier across files. Handles both single-variant and hwmv2 multi-qualifier reference layouts. Binary self-validation checks confirm: files exist, content is correctly renamed, sibling-`common/` dependencies are surfaced, west sees the board, and a hello_world build configures cleanly.
