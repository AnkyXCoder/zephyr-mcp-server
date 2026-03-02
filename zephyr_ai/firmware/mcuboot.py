"""
MCUboot image analysis.
"""

import struct


def analyze_image(image_path: str):
    """
    Basic MCUboot header analysis.
    """

    with open(image_path, "rb") as f:
        header = f.read(32)

    magic = struct.unpack("<I", header[0:4])[0]

    return {
        "magic": hex(magic),
        "size": len(header)
    }
