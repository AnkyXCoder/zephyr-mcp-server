---
name: static-analysis-runner
description: Use when the user asks to statically analyse embedded C/C++ sources -- "run cppcheck on drivers/", "lint this module", "static analysis on my driver", "run clang-tidy", "any static analysis findings before I push". Runs cppcheck (or clang-tidy / another configured linter) over a scoped path, parses the machine-readable output, and reports findings grouped by severity with file:line for each. Never claims "clean" without a captured exit code and a parsed report.
---

# static-analysis-runner

Runs a static analyser over a scoped source path and reports its findings grouped by severity, each with a real `file:line`. Uses the analyser's machine-readable output (cppcheck XML / clang-tidy YAML) rather than scraping human-readable console text.

Replaces the `zephyr_mcp` MCP tool: `run_cppcheck`.

## When to use

- User wants cppcheck or clang-tidy run over a driver, module, or subsystem before pushing.
- User wants findings triaged by severity (error / warning / style / performance).
- User wants a repeatable pre-PR lint gate over a specific path.

## When NOT to use

- The code does not compile and the user wants to know why (use `build-doctor`; static analysis on a broken tree produces noise).
- The user wants runtime test results (use `twister-runner`) or simulation output (use `renode-runner`).
- The user wants Zephyr's own commit/style checks (`scripts/checkpatch.pl`, `west format`) -- those are style gates, not static analysis; say so and point at them rather than substituting cppcheck.
- The user asks to analyse the entire Zephyr tree unscoped -- refuse and ask for a path (see Required inputs).

## Required inputs

| Input | Type | Default |
|-------|------|---------|
| `path` | directory or file to analyse | (none -- ask; refuse an unscoped whole-tree run) |
| `tool` | `cppcheck` or `clang-tidy` | `cppcheck` |
| `enable` | cppcheck `--enable=` value | `all` |
| `report_path` | machine-readable output file | `/tmp/static-analysis-<tool>-<basename>.xml` (cppcheck) / `.yaml` (clang-tidy) |
| `compile_commands` | path to `compile_commands.json` (clang-tidy; also improves cppcheck accuracy) | `<build_dir>/compile_commands.json` if it exists |
| `severity_filter` | only report at/above this severity: `error`, `warning`, `style`, `performance`, `information` | none (report all) |
| `max_findings_listed` | findings printed before truncation | `40` |
| `timeout_s` | analysis timeout | `900` |

If `path` is missing, ask. Whole-tree cppcheck over Zephyr takes tens of minutes and yields thousands of low-value findings from vendor HALs -- always scope it.

## Tool resolution

1. `which cppcheck` (or `which clang-tidy` when `tool = clang-tidy`). If absent, halt and name the missing binary; do not silently substitute the other analyser -- they report different classes of defect.
2. If `compile_commands.json` exists under a build directory, pass it (`cppcheck --project=<file>`, `clang-tidy -p <build_dir>`). Report whether it was used: findings without it are less accurate because macros and include paths are guessed.
3. Record the exact analyser version (`cppcheck --version`) in the report so results are reproducible.

## Procedure

1. **Resolve and verify scope.** `test -e <path>`; halt if it does not exist. If `path` resolves to the whole Zephyr tree or the workspace root, refuse and ask for a narrower scope.
2. **Resolve the tool** per the chain above, capturing its version.
3. **Run the analyser** with machine-readable output:
   - cppcheck: `cppcheck --enable=<enable> --xml --xml-version=2 [--project=<compile_commands>] <path> 2> <report_path>`
   - clang-tidy: `clang-tidy -p <build_dir> --export-fixes=<report_path> <files>`
   Capture the exit code separately from the report. cppcheck exits 0 even when it reports findings unless `--error-exitcode` is set, so **the exit code alone never means "clean"**.
4. **Parse the report.** Extract every finding's `severity`, `id`, `file`, `line`, and `msg`. Tally by severity.
5. **Verify the findings are real.** For each finding printed, confirm the cited file exists (`test -f`) and the line number is within the file's line count. Drop and re-verify anything that fails -- never print a `file:line` that cannot be opened.
6. **Apply `severity_filter`** if given, and state both the filtered count and the true total.
7. **Report** with the output format below. If the report parses and contains zero findings, that is a legitimate "clean" result -- but say "0 findings in `<report_path>`", citing the parsed artifact, not just the exit code.

## Self-Validation Protocol

Every check binary; report all six.

| # | Check | How to verify |
|---|-------|---------------|
| 1 | Scope path exists and is narrower than the whole tree | `test -e <path>`; path is not the workspace/Zephyr root |
| 2 | Analyser binary found, version recorded | `which <tool>` and `<tool> --version` output captured |
| 3 | Exit code captured | record the literal integer |
| 4 | Machine-readable report exists and parses | `test -f <report_path>` and it parses as XML/YAML |
| 5 | Every printed finding has a verifiable location | `test -f <finding.file>` and `line <= wc -l <finding.file>` |
| 6 | "Clean" is backed by a parsed report | a zero-findings claim cites the parsed report, never the exit code alone |

If check 4 fails: report the run as inconclusive with the analyser's stderr tail; do not report "no issues found". If check 5 fails for a finding: drop it and note the drop.

## Retry policy

At most 1 retry, and only for a setup failure: missing `compile_commands.json` (retry without `--project`, clearly labelling the results as lower-accuracy) or a `--enable` value the installed version rejects (retry with `--enable=warning,style`). Never retry to reduce the number of findings.

## Output format

```
static-analysis-runner result: FINDINGS  (or CLEAN / INCONCLUSIVE)

Tool:     cppcheck 2.10                (compile_commands.json: used)
Scope:    drivers/pulse_io
Command:  cppcheck --enable=all --xml --xml-version=2 --project=build/compile_commands.json drivers/pulse_io   (exit 0)
Report:   /tmp/static-analysis-cppcheck-pulse_io.xml  (parsed, 12 findings)

By severity:
  error         1
  warning       4
  style         6
  performance   1

Findings (showing 12 of 12):
  error        drivers/pulse_io/pulse_io_encoder.c:142   nullPointer          Possible null pointer dereference: cfg
  warning      drivers/pulse_io/pulse_io_loopback.c:88   uninitvar            Uninitialized variable: idx
  style        drivers/pulse_io/pulse_io_handlers.c:31   unusedVariable       Unused variable: ret
  ...

Validation:
  [x] scope exists and is narrow:  drivers/pulse_io
  [x] tool + version:              cppcheck 2.10
  [x] exit code:                   0  (note: cppcheck exits 0 even with findings)
  [x] report parses:               XML, 12 entries
  [x] all locations verified:      12/12 file:line resolvable
  [x] result backed by report:     yes
```

## Examples

### Example 1: scoped driver lint

User: "run cppcheck on drivers/pulse_io"

Agent verifies the path, finds cppcheck 2.10, runs it with XML v2 output plus the build's `compile_commands.json`, parses 12 findings, verifies every `file:line` opens, and reports them grouped by severity. It notes explicitly that cppcheck's exit code was 0 despite findings.

### Example 2: clean result, stated honestly

User: "any static analysis issues in my new module?"

The XML report parses with zero `<error>` entries. Agent reports **CLEAN -- 0 findings in the parsed report**, citing the report path and the analyser version, rather than saying "exit code 0, looks fine".

### Example 3: refusal on unscoped run

User: "run cppcheck on the whole Zephyr tree"

Agent refuses: the run takes tens of minutes and the output is dominated by vendor HAL noise that nobody will act on. It asks which subsystem, driver, or module directory to scope to, and offers `drivers/`, a single module path, or the diff's touched files as options.

## Elevator pitch (for slides)

static-analysis-runner wraps cppcheck/clang-tidy the way an MCP tool would, but refuses the two ways static analysis usually lies: it will not call a run "clean" on the strength of an exit code (cppcheck exits 0 with findings), and it will not print a `file:line` it cannot open. Scope is mandatory, so nobody accidentally lints the whole tree.
