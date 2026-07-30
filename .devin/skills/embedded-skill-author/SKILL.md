---
name: embedded-skill-author
description: Use when the user wants to capture a stable, repeatable embedded engineering procedure as a deterministic, self-validating Claude Code skill. Triggers include "make a skill for X", "codify this procedure as a skill", "I want a skill that does Y every time", "turn this checklist into a skill", or any request to build a reusable agent skill around a known-good embedded workflow. Generates a complete `.claude/skills/<name>/SKILL.md` plus a paired multi-run test harness `tests/skills/<name>/runner.sh`. Refuses to author skills for open-ended tasks (debugging novel issues, architecture decisions) where the procedure is not stable.
---

# embedded-skill-author

Authors a deterministic, self-validating Claude Code skill for a stable embedded engineering procedure. The output is a `SKILL.md` that follows the seven-part template (frontmatter + when-to-use + inputs + procedure + self-validation + retry + output format + examples) and a paired test harness that drives the skill via `claude -p`, asserts post-conditions, and gates determinism with a multi-run pass threshold.

## When to use

- The user has a stable embedded procedure they execute repeatedly: HAL-driver bring-up, MISRA deviation generation, memory analysis, BSP scaffolding, build-error triage, peripheral configuration, etc.
- The procedure has a "right answer" that an experienced engineer would teach a junior the same way every time.
- The procedure produces an output (a file, a diff, a diagnosis) that can be verified by a literal shell command — `test -f`, `grep -q`, an exit-code check, or a fixed-format match.

## When NOT to use

- The procedure is open-ended exploration (debugging a novel hardware bug, architecture brainstorming, requirements analysis). Skills codify procedures; they do not problem-solve.
- The procedure is a one-off task. The spec + harness investment exceeds the use value.
- The procedure's "right answer" depends on per-project judgment that cannot be written down. If you cannot enumerate the steps stably, you cannot make a skill stably.

## Required inputs

| Input | Type | Default |
|-------|------|---------|
| `skill_name` | kebab-case identifier (e.g. `hal-driver-scaffold`, `misra-deviation-author`) | (none -- ask) |
| `procedure_summary` | one-paragraph plain-English description of what the skill does | (none -- ask) |
| `triggers` | 3 to 6 example user phrases that should route to this skill | (none -- ask) |
| `inputs` | list of named, typed inputs the procedure needs, with defaults | (none -- ask) |
| `steps` | numbered procedure with explicit halt conditions per step | (none -- ask) |
| `validation_checks` | 3 to 7 binary checks, each with a literal verification command | (none -- ask) |
| `output_format` | example output block showing the fixed structure including the validation table | (none -- ask) |
| `refuse_examples` | 1 to 2 example inputs the skill should explicitly refuse | (none -- ask) |
| `target_dir` | where to write the skill | `.claude/skills/<skill_name>/` |
| `harness_dir` | where to write the test harness | `tests/skills/<skill_name>/` |

If any required input is missing, the skill must interview the user one input at a time. Do not synthesize defaults for the procedure-shaped inputs (steps, validation_checks, output_format) -- those are the user's expertise being captured.

## Procedure

1. **Validate the procedure is stable.** Confirm with the user that:
   - The procedure has a fixed step order.
   - Each step has a deterministic halt condition.
   - At least one step's success is shell-verifiable.
   If the user can't answer yes to all three, halt and explain why this is a poor skill candidate.

2. **Collect inputs** by asking the user one question at a time, in the order listed in the table above. Show the user the answers as a structured summary before proceeding to step 3.

3. **Generate `<target_dir>/SKILL.md`** following the seven-part template:
   - Frontmatter with `name:` and a `description:` that includes the trigger phrases verbatim.
   - `## When to use` and `## When NOT to use` sections (use the user's `procedure_summary` and `refuse_examples`).
   - `## Required inputs` table from the user's `inputs` list.
   - Auto-resolution chain section if any input has a sensible default that can be discovered (env var, `which`, `find`, etc.).
   - `## Procedure` section from the user's `steps`, numbered with explicit halt conditions per step.
   - `## Self-Validation Protocol` table from the user's `validation_checks`.
   - `## Retry policy` (default: maximum 1 retry on the last validation check; the user can override).
   - `## Output format` block from the user's `output_format` example.
   - `## Examples` section with at least one success case and one refusal case.

4. **Generate `<harness_dir>/runner.sh`** that:
   - Sets `set -euo pipefail` and `unset ANTHROPIC_API_KEY` (Max-plan / OAuth keychain hygiene).
   - Defines at least one fixture (input → expected post-condition).
   - Loops `RUNS_PER_FIXTURE` (default 1; full gate uses 5).
   - Invokes the skill via `claude -p "<prompt>" --output-format json --permission-mode acceptEdits`.
   - Parses the JSON `.result` field, applies a grep-based post-condition check.
   - Reports `PASS` / `FAIL` per run, then a per-skill summary.
   - Computes `PASS_THRESHOLD` as ceil(4*N/5) by default; user can override via `PASS_THRESHOLD` env var.
   - Exits 0 on threshold met, 1 otherwise.

5. **Make the harness executable.** `chmod +x <harness_dir>/runner.sh`.

6. **Self-validate the generated artifacts** (next section).

## Self-Validation Protocol

| # | Check | How to verify |
|---|-------|---------------|
| 1 | SKILL.md was written | `test -f <target_dir>/SKILL.md` |
| 2 | Frontmatter parses (has `name:` and `description:`) | `head -5 <target_dir>/SKILL.md \| grep -E '^name:'` and same for `description:` |
| 3 | Seven-part template present | grep for each section header: `When to use`, `Required inputs`, `Procedure`, `Self-Validation Protocol`, `Retry policy`, `Output format`, `Examples` -- count == 7 |
| 4 | Procedure has at least 3 numbered steps | `grep -cE '^[0-9]+\.' <target_dir>/SKILL.md` returns >= 3 |
| 5 | Self-Validation Protocol has at least 3 binary checks | count rows in the validation table |
| 6 | Test harness was written and is executable | `test -x <harness_dir>/runner.sh` |
| 7 | Test harness has at least one fixture and a PASS_THRESHOLD | grep for `PASS_THRESHOLD` and at least one fixture loop |

If check 1, 2, or 6 fails: halt; the file generation failed.
If checks 3, 4, 5, or 7 fail: re-render the missing section once and re-validate.

## Retry policy

Maximum 1 retry on the last validation pass. After that, surface the partial output to the user and explain which sections failed to render.

## Output format

```
embedded-skill-author result: PASS  (or FAIL)

Generated:
  Skill spec:    .claude/skills/<skill_name>/SKILL.md  (XX lines)
  Test harness:  tests/skills/<skill_name>/runner.sh   (executable)

Validation:
  [x] SKILL.md written
  [x] Frontmatter parses (name + description)
  [x] Seven-part template complete
  [x] Procedure: 5 numbered steps
  [x] Self-Validation Protocol: 5 binary checks
  [x] Harness executable
  [x] Harness has 1 fixture, PASS_THRESHOLD computed

Next steps:
  1. Review the generated skill spec and adjust language if needed.
  2. Run the harness once with RUNS=1 to confirm the skill invokes.
  3. Run a full determinism gate when you trust it: RUNS=5 ./tests/skills/<skill_name>/runner.sh
```

## Examples

### Example 1: codify a HAL driver scaffold procedure

User: "I want a skill that scaffolds a vendor HAL driver from a reference. The reference is a known-good driver in our codebase; the skill mirrors the file layout, renames the chip identifier, and stubs the register accessors using the vendor's reference manual section numbers."

Agent:
1. Confirms the procedure is stable (yes -- the user has done it five times by hand).
2. Interviews for `skill_name` (`hal-driver-scaffold`), `inputs` (reference path, target chip name, RM section), `steps`, `validation_checks` (file count, chip-identifier rename, register address grep, dtc-clean compile), `output_format`.
3. Writes `.claude/skills/hal-driver-scaffold/SKILL.md` and `tests/skills/hal-driver-scaffold/runner.sh`.
4. Reports PASS with the seven self-validation checks.

### Example 2: refuse on open-ended task

User: "Make a skill that debugs intermittent hardware faults."

Agent: refuses. Explains: intermittent hardware faults are open-ended exploration; the procedure is not stable (the next fault is rarely the same as the last); shell-verifiable success criteria do not exist. Suggests instead a paired skill `fault-evidence-collector` that codifies the *data-collection* procedure (logic-analyzer capture, register snapshot, build artifact attach) -- which IS stable -- and leaves diagnosis to the engineer.

## Elevator pitch (for slides)

embedded-skill-author turns a stable embedded engineering procedure into a deterministic, self-validating Claude Code skill -- frontmatter, inputs, numbered procedure, binary validation checks, fixed output format, paired multi-run harness. Every claim the new skill makes is grep-verifiable; every run is gated by an N-run determinism threshold. The pattern that produced the original five workshop skills, made into a skill itself.
