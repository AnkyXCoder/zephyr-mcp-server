"""
Devicetree analyzer for Zephyr.
"""


def list_enabled_nodes(dt_file: str):
    """
    Lists nodes marked as status = "okay".
    """

    enabled = []

    with open(dt_file, "r") as f:
        for line in f:
            if 'status = "okay"' in line:
                enabled.append(line.strip())

    return {"enabled_nodes": enabled}
