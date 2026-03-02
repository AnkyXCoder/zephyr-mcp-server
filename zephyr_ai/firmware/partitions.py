"""
Parses Zephyr partition manager output.
"""

import yaml


def parse_partitions(file: str):
    with open(file) as f:
        data = yaml.safe_load(f)

    partitions = []

    for name, info in data.items():
        partitions.append({
            "name": name,
            "address": info.get("address"),
            "size": info.get("size")
        })

    return partitions
