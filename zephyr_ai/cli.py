import typer
import asyncio
from zephyr_ai.core.async_exec import run_async_command

cli = typer.Typer()


@cli.command()
def set_model(name: str):
    from zephyr_ai.ai.llm_engine import OllamaEngine
    engine = OllamaEngine(model=name)
    print(f"Model set to {name}")


@cli.command()
def build(board: str, path: str):
    result = asyncio.run(
        run_async_command(["west", "build", "-b", board, path])
    )
    print(result)


@cli.command()
def dashboard():
    from zephyr_ai.dashboard.app import run_dashboard
    run_dashboard()


@cli.command()
def enforce_code(path: str):
    from zephyr_ai.compliance.code_enforcer import enforce_headers
    from zephyr_ai.compliance.code_formatter import run_clang_format
    from zephyr_ai.compliance.precommit_runner import run_precommit

    enforce_headers(path)
    run_clang_format(path)
    run_precommit()
    print("Code compliance enforced.")


if __name__ == "__main__":
    cli()
