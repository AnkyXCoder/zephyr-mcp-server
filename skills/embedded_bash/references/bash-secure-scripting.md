# Bash Secure Scripting — In-Depth Reference

A principle-level guide for writing safe, robust, and maintainable shell scripts for embedded build, flash, and CI workflows.

---

## Set Options

- `set -euo pipefail` at the top of every script.
  - `-e`: exit on error.
  - `-u`: treat unset variables as an error.
  - `-o pipefail`: the exit code of a pipeline is the first failing command.
- `IFS=$'\n\t'` to split only on newlines and tabs.
- Use `set -x` only for debug output; remove it before committing.

## Quoting and Variables

- Always quote variables: `"$var"`.
- Use `"${array[@]}"` to expand arrays safely.
- Use `"$*"` or `"$@"` appropriately; `"$@"` preserves separate arguments.
- Avoid word splitting and globbing surprises.
- Use `local` in functions to limit scope.
- Use `readonly` for constants and `declare -r` for arrays.

## Avoiding Dangerous Constructs

- **Never `eval`** a string built from user input or file contents.
- **Avoid `source` or `.` of untrusted files.**
- **No `curl | bash` or `wget | sh`.**
- **Do not use backticks;** use `$(...)` instead.
- Do not build command strings and execute them dynamically.
- If dynamic commands are unavoidable, use `command -v` and `printf '%q'`.

## Temp Files and Paths

- Create temp dirs with `mktemp -d`.
- Always `trap 'rm -rf "$workdir"' EXIT`.
- Use `cd -P` or `cd --` to avoid symlink issues.
- Canonicalize paths with `realpath` or `readlink -f` where available.
- Do not `rm -rf` a path that was not explicitly validated.

## Arguments and Validation

- Use `arg1="${1:?message}"` for required arguments.
- Validate numbers with `[[ $n =~ ^[0-9]+$ ]]`.
- Validate board names and build dirs with explicit checks.
- Print usage to `stderr` and exit with a non-zero code.
- Use `getopts` or manual parsing; keep it simple and safe.

## Error Handling

- Check command exit codes with `if` or `||`.
- Use `set -e` and `set -o pipefail` to fail fast.
- Provide meaningful error messages on `stderr`.
- Use `trap` for cleanup on `EXIT`, `ERR`, and `INT`.

## Tooling

- Run `shellcheck -x script.sh` before committing.
- Use `bash -n script.sh` for a syntax-only check.
- Keep scripts under a few hundred lines; otherwise, prefer Python.

## Security

- Do not pass secrets on the command line; use env vars or files with `0400` perms.
- Avoid `sudo` in scripts; if needed, warn and document.
- Validate all external inputs before using them in commands.
- Quote all path and name variables passed to `west`, `ninja`, `make`, etc.
