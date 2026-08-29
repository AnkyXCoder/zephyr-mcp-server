# Python for Embedded Tooling — In-Depth Reference

A principle-level guide for Python scripts that support embedded firmware: build/test runners, flashing helpers, serial loggers, and CI tooling.

---

## Style and Formatting

- Follow PEP 8; use `ruff` for linting and `ruff format` for formatting.
- Use type hints in every function and keep `mypy --strict` clean.
- Prefer explicit imports; avoid `from module import *`.
- Keep functions small and single-purpose.
- Use `pathlib.Path` instead of `os.path`.
- Prefer dataclasses or `NamedTuple` over raw dictionaries for structured data.

## Type Safety

- Annotate all public function signatures.
- Use `Optional[...]`, `Union[...]`, or `X | Y` consistently.
- Use `TypedDict` or dataclasses for config/JSON schemas.
- Avoid `Any`; if it is required, document why.
- Run `mypy --strict` as a CI gate.

## Security

- **Never use `eval` or `exec` on untrusted or user-supplied data.**
- Use `ast.literal_eval` only for literal values; validate first.
- Use `subprocess.run` with `shell=False` and a list of arguments.
- Never pass user input directly to `subprocess` without validation.
- Use `yaml.safe_load`; never `yaml.load`.
- Do not `pickle` untrusted data.
- Load secrets from environment variables, never from committed files.
- Use `bandit` to scan for common vulnerabilities.

## Input Validation

- Validate `argparse` arguments with `type` and `choices` where possible.
- Canonicalize file paths with `Path.resolve()`.
- Check that serial ports, build directories, and config files exist.
- Reject unexpected characters in paths and identifiers.
- Use `try/except` with specific exceptions; do not use bare `except:`.

## Subprocess and Serial

- `subprocess.run([...], check=True, capture_output=True, text=True)` is the default.
- Add `timeout=` to all long-running calls.
- Use `shlex.quote` only if `shell=True` is unavoidable, but avoid `shell=True`.
- For serial, use `pyserial` with a timeout and a context manager.
- Close all resources in `finally` or with context managers.

## Logging and Output

- Use the `logging` module, not `print`.
- Do not log secrets, tokens, or user credentials.
- Exit with clear, documented codes.
- Report structured output where possible (JSON for machine consumers).

## Testing

- Use `pytest`.
- Keep tests FIRST and independent.
- Mock `subprocess` and serial ports in unit tests.
- Use `tmp_path` for filesystem tests.
