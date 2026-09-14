"""
Kconfig symbol search and validation.
"""

import os


def search_kconfig(symbol: str, zephyr_base: str):
    """
    Search for Kconfig symbol in Zephyr base directory.
    """

    matches = []

    for root, _, files in os.walk(zephyr_base):
        for file in files:
            if file.startswith("Kconfig"):
                path = os.path.join(root, file)
                with open(path, "r", errors="ignore") as f:
                    if symbol in f.read():
                        matches.append(path)

    return {
        "symbol": symbol,
        "found_in": matches
    }
