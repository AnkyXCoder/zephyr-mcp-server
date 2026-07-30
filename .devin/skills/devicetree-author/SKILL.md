---
name: devicetree-author
description: Use when the user asks to add, enable, modify, or wire up a device tree node, peripheral, or pin in a Zephyr board's .dts or .overlay file. Triggers include "add an I2C sensor", "enable lpuart0 as console", "wire up the LED node", "add a gpio-leds child", "edit the devicetree", "create an overlay". Edits or creates DT files with explicit binding YAML citations and reference manual section references for every register / pin reference.
---

# devicetree-author

Adds or modifies device tree nodes in a Zephyr `.dts` or `.overlay` file. Cites the binding YAML for every node and the SoC's reference manual section for every peripheral or pin reference. Validates that dtc accepts the result.

## When to use

- User wants to enable a peripheral that exists in the SoC dtsi but is `disabled` (set `status = "okay"`).
- User wants to add a child node to a bus (e.g. an I2C sensor under an i2c controller).
- User wants to add a top-level helper node (gpio-leds, gpio-keys, etc.).
- User wants to add an overlay alias or set a property on an existing node.

## When NOT to use

- The user wants to change a Kconfig setting (use `kconfig-tuner`).
- The user wants to scaffold an entirely new board (use `zephyr-bsp-scaffold`).
- The user is debugging a build error (use `build-doctor`).

## Required inputs

| Input | Type | Default |
|-------|------|---------|
| `target_file` | path to the `.dts` or `.overlay` file to edit | (none -- ask) |
| `action` | one of: `enable-node`, `add-child`, `add-overlay-node`, `set-property` | (none -- ask) |
| `compatible` | DT compatible string (for `add-child` / `add-overlay-node`) | (depends) |
| `parent_label` | parent node label (for `add-child`) | (depends) |
| `rm_section` | reference manual section to cite for the peripheral/pin reference | (asked when adding peripheral/pin reference) |
| `zephyr_root` | path to the Zephyr source tree (used to locate bindings) | auto-detect (see below) |
| `project_path` | path to the Zephyr application/project (where `west build` runs) | inferred from current dir |
| `board_target` | Zephyr build target (e.g. `frdm_mcxa156/mcxa156`, `nrf52840dk/nrf52840`) | (asked at validation time) |
| `build_invocation` | how to run `west build` for dtc validation | auto-detect (see below) |

## Zephyr root resolution

Try in order, take the first that resolves:

1. `ZEPHYR_BASE` environment variable, if set and the directory exists.
2. `west topdir` if `west` is on PATH; the result is the workspace root, and `zephyr_root = <workspace>/zephyr`.
3. `/workdir/zephyr` (common container layout).
4. `./zephyrproject/zephyr` (common host layout).
5. Ask the user.

## Build-invocation resolution

For the dtc-validation step in the procedure:

1. If `west` is on PATH, run `west build` directly.
2. Otherwise, look for a project-local container wrapper script (e.g. `./build.sh`) and use it.
3. Otherwise, if a `docker-compose.yml` exists, use `docker compose run --rm <service> west build`.
4. Otherwise, ask the user how to run a Zephyr build.

## Procedure

1. **Read the current file** and show the user the section being edited.

2. **Identify the binding YAML** for the new compatible string. Run:
   ```
   find <zephyr_root>/dts/bindings -name "*$(echo <compatible> | tr ',' '*')*" 2>/dev/null
   ```
   If no binding is found, halt and tell the user.

3. **Halt on ambiguity. Never make an executive decision.** Stop and ask the user when:
   - **Address / register conflict.** The proposed `reg` (I2C address, register offset, IRQ number) collides with an already-present node. Surface the conflict, list the realistic resolutions (move one address via strap resistor, disable one node, swap onto a different bus), and let the user pick. Do not silently drop one.
   - **Source data ambiguity.** A pinout sheet has a duplicate row, a TBD status, a conflicting "old vs new" column, or any field the agent cannot ground in a single answer. Quote the ambiguity, do not pick.
   - **Compatible-string ambiguity.** Multiple bindings match the proposed `compatible` (e.g. `bosch,bme280` has separate `-i2c` and `-spi` flavors). Ask which the user's hardware uses; the bus-parent's type is the usual disambiguator but should be confirmed.
   - **Property defaults the spec does not carry.** I2C clock-frequency, drive strength, slew rate, pull-up state. The source spec may not say. Ask, do not default silently. Acceptable to suggest the conservative default with a one-line reason and ask the user to confirm.

4. **Construct the edit.** Apply a minimal, targeted change. Keep existing nodes intact.

   **Never strip SoC-internal nodes when refactoring a derived BSP.** When this skill is editing a `.dts` that was scaffolded from a reference, leave the SoC-platform-service nodes (`timer*`, `wdt*`, `usbd` / `zephyr_udc0`, `qmi` / quad-SPI controllers, clocks, RTC) alone unless the user has explicitly asked you to disable them. Strip only board-specific nodes that the user has named as no-longer-applicable (vendor LEDs, on-board sensors that aren't on the derived board, etc.). When in doubt, leave it enabled.

   **Pinctrl groups go in a separate file by default.** When authoring a new pinctrl group on a board that does not yet have a `<board>-pinctrl.dtsi` sibling file, create one and put the group there, then have the main `.dts` (or `.dtsi`) `#include "<board>-pinctrl.dtsi"`. This keeps pinmux scalable as the board grows. The exception: if the user explicitly prefers pinctrl inline, or if the reference BSP keeps pinctrl inline and the user has chosen to preserve that layout, document the choice in your output and proceed.

   **Preserve or set board-root identity (`model` + `compatible`).** Every Zephyr board's main `.dts` or `.dtsi` MUST have `model = "<human-readable name>"` and `compatible = "<vendor,board>"` at the root `/` node. When rewriting a board file inherited from a derived BSP (e.g., the scaffold mirrored a reference), update these to reflect the new board's identity — do not silently leave the reference's values, and do not drop them. If the inputs do not carry a vendor identifier, halt and ask. These two properties are how Zephyr identifies the board to bindings and to log output; missing them works for hello_world but breaks downstream binding-overlay matching.

   **GPIO bank-boundary validation.** Many SoCs expose GPIOs across multiple bank nodes (low/high splits like `gpio0_lo` / `gpio0_hi`, per-port banks like `gpioa` / `gpiob`, or banked controllers like NXP's per-PORT GPIO instances). When authoring a pin reference of the form `<&<bank> <pin_index>>` or `<&<bank> (<PIN#> - <OFFSET>)>`:

   - Determine the chosen bank's actual pin range (e.g., by reading the SoC dtsi for that bank's `gpio-controller` properties or `ngpios`, or by consulting the SoC's reference manual).
   - Verify the resolved literal pin index falls inside that range.
   - Arithmetic indices like `<&gpio_hi (N - 32)>` MUST evaluate to a non-negative integer. If `N < 32`, you have selected the wrong bank — that pin lives in the low bank.
   - dtc does not catch negative pin indices reliably; the build may pass while the runtime behavior is silently wrong.

   If the source spec gives only a global pin number (e.g., "GPIO29") and the SoC has multiple banks, determine which bank owns that pin before writing the reference. If unsure, halt and ask.

5. **Cite the binding YAML path** in a comment above the new node (or in the diagnosis output). Format: `/* binding: dts/bindings/<class>/<file>.yaml */`.

6. **For peripheral or pin references** (e.g. a register address, a clock-frequency cap), cite the SoC's reference manual section. Format: `/* RM: <section>, <topic> */`. If the source is a schematic sheet rather than an RM (common for board-bringup pinouts), substitute with `/* Sch: <sheet>, <topic> */` and annotate the substitution.

7. **Run dtc validation** via the resolved build invocation. Build into a scratch directory so the user's main build is untouched:
   ```
   <build_invocation> -p always -b <board_target> <project_path> -d /tmp/dts-check
   ```
   Look for "devicetree error" and "Error:" in stderr.

8. **Verify the new node appears** in `<build_dir>/zephyr/zephyr.dts` (the generated final DT). Default `<build_dir>` is `/tmp/dts-check`.

9. **Final-edit production-readiness audit** (run once, after the last edit in a bulk-authoring session — not per edit):

   - **SoC platform services audit.** Compare the SoC-service nodes enabled in the *reference* BSP against those enabled in the *derived* BSP. For each reference-enabled service that is now disabled or absent (timer, wdt, usbd, etc.), surface it and ask whether to enable it on the derived board. The xlsx is almost always silent on these; the user must decide explicitly.
   - **SoC-required boot/partition artifacts.** Some SoC families require specific partition layouts or boot blocks (a header at flash offset 0, a partition table, special boot pins, etc.). Check whether the reference BSP enables a `fixed-partitions` block or a boot-header node; if it does, the derived BSP probably needs the equivalent. Prompt the user before completing; do not silently omit.

## Self-Validation Protocol

Per-edit checks (run after every edit):

| # | Check | How to verify |
|---|-------|---------------|
| 1 | Target file exists | `test -f <target_file>` |
| 2 | Edit was applied | `grep -q '<distinguishing token>' <target_file>` (e.g. the new compatible string) |
| 3 | Binding YAML cited and exists | extract the path from the comment; `test -f <zephyr_root>/<binding>` succeeds |
| 4 | RM (or Sch) section cited (if peripheral/pin reference) | grep `RM:` or `Sch:` in the new content |
| 5 | No silent ambiguity resolution | Any address conflict, source-data duplicate, or compatible-string ambiguity surfaced to the user before this edit was applied. If the agent picked between options without asking, this check FAILS. |
| 6 | Pinctrl placement matches convention | If the edit creates a new pinctrl group AND the project has a `<board>-pinctrl.dtsi`, the group went there (not inline). If no such file existed, this skill created one. Inline placement is acceptable only with an explicit user opt-in noted in the output. |
| 6b | Multi-bank GPIO pin indices are in-range | For every pin reference in the edit of the form `<&<bank> <pin_or_expr>>`, evaluate the index literal. If it is negative OR exceeds the bank's `ngpios`/range, this check FAILS — the wrong bank was selected (or the arithmetic offset is wrong). For any non-literal arithmetic (`(N - K)` expressions), perform the substitution and check the result. dtc does not catch this; the per-edit check is the only line of defense before the bug ships. |
| 7 | dtc compiles cleanly | the build reaches "Configuring done" without devicetree errors |
| 8 | New node appears in zephyr.dts | `grep -q '<distinguishing token>' <build_dir>/zephyr/zephyr.dts` |

If check 3 fails: the binding does not exist. Re-search with broader patterns or halt.
If check 5 fails: revert the edit and re-run after surfacing the ambiguity to the user.
If check 7 or 8 fails: invoke build-doctor on the captured stderr.

End-of-session audit (run once, after the last edit in a bulk-authoring session):

| # | Check | How to verify |
|---|-------|---------------|
| A1 | SoC platform services preserved | For each `compatible` enabled in the reference BSP's SoC-internal node set (`timer*`, `wdt*`, `usbd`/`zephyr_udc0`, `qmi`, clocks, RTC), the derived BSP has either kept it enabled or surfaced the disable for explicit user confirmation. |
| A2 | SoC-required boot artifacts surfaced | If the reference BSP has a `fixed-partitions` block, a boot-header node, or any partition layout the derived board likely also needs, the agent surfaced it to the user for explicit confirmation. |
| A3 | User confirmations recorded | Every "halt and ask" decision from step 3 has the user's recorded answer cited in the final output. |
| A4 | Board root has `model` + `compatible` | After all edits, the board's main `.dts` or `.dtsi` has both `model = "..."` and `compatible = "vendor,board"` at the root `/` node, reflecting the new board's identity (not the reference's). FAILS if either is missing or if the reference's identity was left in place. |

## Retry policy

Maximum 1 retry on check 5 / 6 failure (re-read stderr and adjust the edit). After that, escalate.

## Output format

```
devicetree-author result: PASS  (or FAIL)

Edit:
  File:        <target_file>
  Action:      enable-node
  Node label:  &lpuart0
  Citation:    binding <zephyr_root>/dts/bindings/serial/nxp,lpuart.yaml
               RM section 42.3 (LPUART register map)

Validation (per-edit):
  [x] target file exists
  [x] edit applied
  [x] binding cited:           dts/bindings/serial/nxp,lpuart.yaml
  [x] RM/Sch cited:            42.3
  [x] no silent resolution:    no ambiguity in this edit
  [x] pinctrl placement:       inline (no pinctrl group created in this edit)
  [x] bank/pin indices:        all pin references in-range for chosen bank
  [x] dtc clean:               Configuring done
  [x] node in zephyr.dts:      lpuart@4009f000 status="okay"
```

End-of-session audit (when a bulk-authoring run is complete):

```
End-of-session audit:
  [x] SoC platform services preserved:  <list of services confirmed enabled>
  [ ] SoC boot artifacts surfaced:      <reference has fixed-partitions; derived board not confirmed -- ASK USER>
  [x] User confirmations recorded:      <list of step-3 halts with the user's answer>
  [x] Board root has model + compatible: model = "<board human name>"; compatible = "<vendor,board>"
```

## Examples

### Example 1: enable a UART node as the console

User: "enable lpuart0 in my workshop board"

Edit: `&lpuart0 { status = "okay"; current-speed = <115200>; pinctrl-0 = <&pinmux_lpuart0>; pinctrl-names = "default"; };`

Citations:
- binding `<zephyr_root>/dts/bindings/serial/nxp,lpuart.yaml`
- RM section for the LPUART peripheral on the target SoC

### Example 2: add an I2C sensor as a child node

User: "add a BME280 sensor at I2C address 0x76 under lpi2c0"

Edit (under `&lpi2c0`):
```
bme280: bme280@76 {
    compatible = "bosch,bme280";
    reg = <0x76>;
};
```

Citations:
- binding `<zephyr_root>/dts/bindings/sensor/bosch,bme280-i2c.yaml`
- RM section for the I2C controller on the target SoC

## Elevator pitch (for slides)

devicetree-author edits `.dts` and overlay files with binding-YAML citations and reference-manual section references baked into every change. Six binary checks confirm: file exists, edit applied, binding cited and on disk, RM cited where appropriate, dtc compiles, new node in the generated zephyr.dts.
