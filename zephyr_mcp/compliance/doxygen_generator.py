"""
Auto-generates Doxygen comments for C functions.
"""

import re


def generate_doxygen_comments(file_path: str):
    with open(file_path, "r") as f:
        content = f.read()

    pattern = re.compile(
        r"\n([a-zA-Z_][a-zA-Z0-9_*\s]+)\s+([a-zA-Z_][a-zA-Z0-9_]*)\((.*?)\)\s*\{")

    def replacer(match):
        return f"""
/**
 * @brief {match.group(2)} function
 *
 * @param {match.group(3)}
 * @return TBD
 */
{match.group(0)}
"""

    new_content = pattern.sub(replacer, content)

    with open(file_path, "w") as f:
        f.write(new_content)
