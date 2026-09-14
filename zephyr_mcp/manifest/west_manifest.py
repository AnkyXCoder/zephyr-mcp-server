"""
West manifest analyzer.
"""

import yaml


def analyze_manifest(manifest_path: str):
    """
    Parses west.yml manifest.
    """

    with open(manifest_path, "r") as f:
        data = yaml.safe_load(f)

    projects = data.get("manifest", {}).get("projects", [])

    return {
        "project_count": len(projects),
        "projects": [p.get("name") for p in projects]
    }
