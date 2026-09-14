---
name: twister-runner
description: Use when the user wants to run Zephyr's Twister test harness -- "run twister on tests/drivers/gpio", "run the twister suite for native_sim", "did my test pass under twister", "run the unit tests", "twister this platform". Runs `west twister` with an explicit JSON report directory, parses `twister.json`, and reports pass/fail/skip/error counts plus the names of failing test instances. Never reports a result that is not in the JSON report.
---

# twister-runner

Runs Zephyr's Twister harness through `west twister`, captures a machine-readable `twister.json` report, and summarizes it. Counts and failure names come from the parsed report, never from scraping console output.

Replaces the `zephyr_ai` MCP tool: `run_twister`.

## When to use

- User wants a test suite or a single test directory run under Twister.
- User wants a platform-scoped regression check (`-p native_sim`, `-p qemu_x86`, a real board).
- User wants to know which specific test instances failed, not just that "tests failed".
- User wants a repeatable pre-PR gate over `tests/` or `samples/`.

## When NOT to use

- The user wants a single application built or flashed (use `west-build-flash`).
- The user wants an ELF run in Renode with a UART string assertion (use `renode-runner`).
- A build error needs classification (use `build-doctor` -- Twister failures that are build failures should be handed there with the failing instance's build log).
- The user wants static analysis rather than execution (use `static-analysis-runner`).

## Required inputs

| Input | Type | Default |
|-------|------|---------|
| `testsuite_root` | path passed to `-T`, e.g. `tests/drivers/gpio` | (none -- ask; refuse to run the whole tree by accident) |
| `platform` | platform passed to `-p`, e.g. `native_sim`, `qemu_cortex_m3`, `nrf52840dk/nrf52840` | (none -- ask; running all platforms is hours of work) |
| `outdir` | report directory passed to `-o` | `<workspace_root>/twister-out/<timestamp>` |
| `extra_args` | additional Twister flags, e.g. `--device-testing`, `-v`, `--tag <tag>` | none |
| `timeout_s` | overall timeout | `1800` |
| `workspace_root` | west workspace root | auto-detect (same chain as `west-workspace-inspector`) |
| `max_failures_listed` | failing instances printed before truncation | `25` |

If `testsuite_root` or `platform` is missing, ask. A full unscoped Twister run can take hours and saturate the machine; never launch one on an inferred default.

## Workspace resolution

Try in order, take the first that resolves:

1. `ZEPHYR_BASE` env var → workspace root is its parent when that contains `.west/`.
2. `west topdir`.
3. Walk up from the current directory looking for `.west/`.
4. Ask the user.

## Procedure

1. **Resolve** `workspace_root` and verify `test -d <workspace_root>/<testsuite_root>` (or that `testsuite_root` is an existing absolute path). Halt if the suite path does not exist -- Twister would otherwise run zero tests and exit 0, which looks like a pass.
2. **Choose the report directory.** Use `outdir`; create it. Keep it out of the source tree (default `twister-out/<timestamp>`) so repeated runs do not overwrite one another and results stay attributable.
3. **Run** from `workspace_root`, backgrounding if it exceeds the foreground wait:
   `west twister -T <testsuite_root> -p <platform> -o <outdir> [extra_args]`
   Capture the exit code and tee console output to `<outdir>/twister-console.log`.
4. **Locate the JSON report** at `<outdir>/twister.json`. If it is absent, the run did not get far enough to produce results -- report that fact plus the console tail, and do **not** invent counts from console text.
5. **Parse** `twister.json`. For each entry in `testsuites[]`, read its `status` (`passed`, `failed`, `error`, `skipped`, `filtered`) and tally. Collect the `name` + `platform` + `reason` of every non-passing, non-filtered instance.
6. **Classify failures.** Separate build failures (`status = error` with a build log) from runtime test failures (`status = failed`). For build failures, offer the failing instance's `<outdir>/<platform>/<suite>/build.log` to `build-doctor` rather than diagnosing here.
7. **Report** with the output format below. Exit code and JSON tallies must both appear; if they disagree (exit 0 with failures listed, or exit 1 with none), say so explicitly rather than picking the convenient one.

## Self-Validation Protocol

Every check binary; report all six.

| # | Check | How to verify |
|---|-------|---------------|
| 1 | Test suite path exists | `test -d <testsuite_root>` (absolute or workspace-relative) |
| 2 | Twister exit code captured | record the literal integer |
| 3 | JSON report exists and parses | `test -f <outdir>/twister.json` and `python3 -m json.tool <outdir>/twister.json > /dev/null` |
| 4 | Counts are internally consistent | passed + failed + error + skipped + filtered == total instances in `testsuites[]` |
| 5 | Zero-test runs flagged | if total instances == 0, report **FAIL / no tests ran**, never PASS |
| 6 | Every listed failure appears in the report | each named instance is grep-findable in `twister.json` |

If check 3 fails: report the run as inconclusive with the console tail. If check 4 fails: report the raw per-status counts and state that they do not sum -- do not silently rebalance them.

## Retry policy

No automatic re-run of failing tests. A flaky-looking failure is information, and re-running silently hides it. At most 1 retry of the *whole* invocation, and only when Twister itself failed to start (e.g. `west: unknown command twister`, missing `-o` directory permissions) -- never to turn a red result green. If the user wants flake detection, suggest Twister's own `--retry-failed <n>` explicitly as an `extra_args` value so it appears in the reported command line.

## Output format

```
twister-runner result: FAIL  (or PASS)

Command:  west twister -T tests/drivers/gpio -p native_sim -o twister-out/20260822-1014   (exit 1, 214s)
Report:   twister-out/20260822-1014/twister.json  (parsed)

Summary:  18 instances
  passed    15
  failed     2
  error      1
  skipped    0
  filtered   0

Failures:
  tests/drivers/gpio/gpio_basic_api  native_sim  failed   assertion failed at test_gpio_pin_toggle
  tests/drivers/gpio/gpio_api_1pin   native_sim  failed   timeout waiting for output
  tests/drivers/gpio/gpio_enable_cb  native_sim  error    build failure -> build.log

Build failures can be diagnosed with build-doctor:
  twister-out/20260822-1014/native_sim/tests_drivers_gpio_gpio_enable_cb/build.log

Validation:
  [x] suite path exists:     tests/drivers/gpio
  [x] twister exit code:     1
  [x] JSON report parses:    twister.json
  [x] counts consistent:     15+2+1+0+0 = 18
  [x] non-zero instances:    18
  [x] failures traceable:    3/3 found in report
```

## Examples

### Example 1: scoped suite run

User: "run twister on tests/drivers/gpio for native_sim"

Agent verifies the suite directory exists, runs Twister with an explicit `-o twister-out/<timestamp>`, parses `twister.json`, and reports 15 passed / 2 failed / 1 error with the failing instance names and reasons. It hands the build-failure instance's `build.log` path to `build-doctor` rather than classifying the compile error itself.

### Example 2: zero tests ran

User: "run twister on tests/drivers/gpi0 for native_sim" (typo).

Agent halts at check 1: the path does not exist. Had the path existed but matched no test instances, it would report **FAIL / no tests ran** rather than PASS, because Twister exits 0 on an empty selection and that would otherwise read as a green run.

### Example 3: refusal to run unscoped

User: "just run twister"

Agent asks for `testsuite_root` and `platform` first, explaining that an unscoped run over the whole tree across all platforms takes hours and saturates the machine. It does not pick a default.

## Elevator pitch (for slides)

twister-runner runs Zephyr's own test harness and reports only what the JSON report says -- consistent tallies, named failing instances, and an explicit **no tests ran** failure mode so an empty selection can never masquerade as a pass. Build-failure instances are routed to build-doctor instead of being guessed at.
