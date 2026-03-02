"""
Runs clang-format using project .clang-format.
"""

import subprocess
import os

from zephyr_ai.core.utils import build_subprocess_env


def run_clang_format(directory: str):
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith((".c", ".cpp", ".h", ".hpp")):
                subprocess.run([
                    "clang-format",
                    "-i",
                    os.path.join(root, file)
                ], env=build_subprocess_env(), check=False)
