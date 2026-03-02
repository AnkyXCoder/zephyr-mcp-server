"""
Runs pre-commit hooks.
"""

import subprocess

from zephyr_ai.core.utils import build_subprocess_env


def run_precommit():
    subprocess.run(
        ["pre-commit", "run", "--all-files"], env=build_subprocess_env(), check=False
    )
