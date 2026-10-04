"""Capability extraction + path sensitivity from YAML taxonomy.

Heuristic v1 (name/description regex). Deterministic and explainable —
good enough for the MVP cut; embedding-assisted mapping is a stretch
extension, not a replacement.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

_DATA = Path(__file__).parent / "data"

# Capabilities that make a tool privileged (approval-gated in enforcing mode).
PRIVILEGED_CAPS = {"EXTERNAL_TRANSFER", "CREDENTIAL_READ", "SHELL_EXEC", "EMAIL_SEND"}


@lru_cache(maxsize=1)
def _taxonomy() -> dict:
    return yaml.safe_load((_DATA / "CAPABILITY_TAXONOMY.yaml").read_text())


@lru_cache(maxsize=1)
def _sensitivity_map() -> dict:
    return yaml.safe_load((_DATA / "SENSITIVITY_MAP.yaml").read_text())


def extract_capabilities(name: str, description: str = "") -> set[str]:
    """Return capability set for a tool; adds PRIVILEGED when derived."""
    haystack = f"{name} {description}".lower()
    caps: set[str] = set()
    for rule in _taxonomy()["rules"]:
        if any(re.search(pat, haystack) for pat in rule["any"]):
            caps.add(rule["capability"])
    if caps & PRIVILEGED_CAPS:
        caps.add("PRIVILEGED")
    return caps


def sensitivity_for_path(path: str) -> str:
    """First-match data class for a file/argument path (default PUBLIC)."""
    lowered = path.lower()
    for rule in _sensitivity_map()["rules"]:
        if re.search(rule["pattern"], lowered):
            return rule["data_class"]
    return "PUBLIC"
