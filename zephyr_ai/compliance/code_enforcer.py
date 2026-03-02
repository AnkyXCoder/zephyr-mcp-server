"""
Enforces file headers and formatting rules.
"""

import os


HEADER_TEMPLATE = """/**
 * @file {filename}
 * @brief {brief}
 *
 * @author AI DevSecOps Platform
 * @date Generated Automatically
 *
 * @copyright
 * (C) Company Name. All rights reserved.
 */
"""


def enforce_headers(directory: str):
    """
    Adds header to C/C++ files if missing.
    """

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith((".c", ".cpp", ".h", ".hpp")):
                path = os.path.join(root, file)

                with open(path, "r+") as f:
                    content = f.read()

                    if not content.startswith("/**"):
                        header = HEADER_TEMPLATE.format(
                            filename=file,
                            brief="Auto-generated header"
                        )
                        f.seek(0)
                        f.write(header + "\n" + content)
