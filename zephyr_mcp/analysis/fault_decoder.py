"""
Decodes Zephyr hardfault logs.
"""

import re


def decode_fault(log: str):
    stack = re.findall(r"0x[0-9a-fA-F]+", log)

    return {
        "stack_addresses": stack,
        "suggestion": "Use addr2line with zephyr.elf for symbol decoding."
    }
