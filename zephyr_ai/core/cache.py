
"""
In-memory + file cache for expensive operations.
"""

import hashlib
import json
from pathlib import Path

CACHE_DIR = Path(".zephyr_ai_cache")
CACHE_DIR.mkdir(exist_ok=True)


def _hash_key(data: str):
    return hashlib.sha256(data.encode()).hexdigest()


def cache_result(key: str, value: dict):
    file = CACHE_DIR / _hash_key(key)
    with open(file, "w") as f:
        json.dump(value, f)


def get_cached(key: str):
    file = CACHE_DIR / _hash_key(key)
    if file.exists():
        return json.load(open(file))
    return None
