"""
Runs cppcheck and parses XML output.
"""

from zephyr_ai.core.utils import run_command


def run_cppcheck(path: str):
    """
    Run cppcheck on given directory.
    """

    return run_command(["cppcheck", "--enable=all", path])
